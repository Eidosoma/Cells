"""S5's own crossrev world set (docs/CELL_DIVISION_S5_DESIGN.md §8.4): programs and bindings.

The set is recorded with validation/tissue/composite_crossrev's own tracing and records
(_setup, _traced, const_record, check_constants), in its file format, so composite_crossrev's
compare checks two revisions' outputs. The worlds are S5's compositions: the partition alone,
asymmetric with mismatch carriers, with a neighbour contact, idle, with a bridge through
1 -> 2 -> 4 and an injection, and the furrow worlds (insertion@2, lumen@2, the bridge) through one
and two cleavages. They live here, not in composite_crossrev: that module's injection set imports
a J1 module, and the J2 bright line bars a module from holding a J1 source and a partition source
(S5's compact worlds) together.

`check` tests §8.4's promise on the saved outputs: E_ref and q_ref (view_energy_reference_pJ,
view_plate_reference_C) and partition_birth_gate are bindings, never compiled in.
* Each is saved among every world's bound layout arrays.
* Two value twins: a world and its copy with the cells' declared charges scaled by about 1.01
  (through the fixed background; the daughters' re-split by the anchor rule) and, in the
  neighbour world, the contact's declared gate moved. The twin's three references differ
  (E_ref and q_ref only, in a world whose one junction is the fixed-open bridge), and its
  traced programs must equal the original's in text and in every closed-over constant. A value
  compiled in would show in one or the other: a scalar as a literal in the text, an array among
  the constants.
* No non-zero reference coincides with a closed-over constant of its own world's programs
  (dtype, shape and bytes). An all-zero array is not distinguishable this way and is reported.

Usage (PYTHONPATH at the revision under test; WORLD names restrict jaxprs and bindings to those
worlds, as the bright line's fresh-process test does; a record of the set takes them all):
  python -m validation.division.division_crossrev jaxprs DIR [WORLD ...]
  python -m validation.division.division_crossrev bindings DIR [WORLD ...]
  python -m validation.division.division_crossrev check DIR
  python -m validation.tissue.composite_crossrev compare A B
"""

import copy
import hashlib
import json
import math
import sys
from pathlib import Path

import numpy as np

from cells.core import partition_spec as ps
from cells.processes.electrochemistry import CHARGE_PER_FMOL
from tests import partition_fixtures as fx
from validation.tissue import composite_crossrev as crossrev

E_REF, Q_REF, BIRTH_GATE = (
    "layout.view_energy_reference_pJ",
    "layout.view_plate_reference_C",
    "layout.partition_birth_gate",
)
BOUND = (E_REF, Q_REF, BIRTH_GATE)
KINDS = ("checked_step", "rhs", "device_checks")
CHARGE_SCALE = 1.01
TWIN_GATE = 0.7  # The neighbour contact's declared gate in its twin (the fixtures' is 0.8).
# {twin: (original, the references its values move)}.
TWINS = {
    "division_neighbour_values": ("division_neighbour", BOUND),
    "division_quartered_values": ("division_quartered", (E_REF, Q_REF)),
}


def revalued(raw, *, charge_scale=CHARGE_SCALE, gate=None):
    """A copy of raw whose values move and whose structure does not.

    Every cell that is no division's daughter has its declared charge scaled by about
    charge_scale: its fixed background moves by (charge_scale - 1) Q / (1e-15 F) and its charge
    anchor is recomputed from it as the tissue's definition check computes it (inventory,
    background and anchor agree). Each division's daughters take the re-split of their parent's
    background and anchor (core/partition_spec.split, the anchor rule add_division applies), in
    declared order. With gate, every junction but a bridge declares that initial gate."""
    raw = copy.deepcopy(raw)
    valence = {s["id"]: s["valence"] for s in raw["model"]["species"]}
    cells = {c["id"]: c for c in raw["model"]["cells"]}
    operators = {op["law"]: op for op in raw["model"]["operators"]}
    divisions = operators[fx.PARTITION]["divisions"]
    daughters = {d for block in divisions for d in block["daughters"]}
    for name, cell in cells.items():
        if name not in daughters:
            shift = (charge_scale - 1.0) * cell["initial_charge_C"] / CHARGE_PER_FMOL
            cell["fixed_charge_equivalent_fmol"] += shift
            content = (valence[s] * n for s, n in cell["initial_amount_fmol"].items())
            cell["initial_charge_C"] = CHARGE_PER_FMOL * math.fsum(
                (cell["fixed_charge_equivalent_fmol"], *content)
            )
    for block in divisions:  # A parent's block precedes its daughters' own.
        parent = cells[block["parent"]]
        for key in ("fixed_charge_equivalent_fmol", "initial_charge_C"):
            for k, daughter in enumerate(block["daughters"]):
                cells[daughter][key] = ps.split(parent[key], block["volume_fraction"])[k]
    if gate is not None:
        bridges = {b["junction_id"] for b in operators.get(fx.BRIDGE, {}).get("bridges", ())}
        for junction in raw["model"]["junctions"]:
            if junction["id"] not in bridges:
                junction["gate"]["initial_gate"] = gate
    return raw


def division_worlds():
    """S5's compositions (module docstring), small, each with pending slots."""
    carriers = {"Na": 0.5, "K": 0.5}
    neighbour = fx.divided(neighbour=True)
    quartered = fx.cleft_quartered(injection=1e-12)
    return dict(
        division_compact=fx.divided(),
        division_asymmetric=fx.divided(f=0.75, area_fraction=0.6, carriers=carriers),
        division_neighbour=neighbour,
        division_neighbour_values=revalued(neighbour, gate=TWIN_GATE),
        division_idle=fx.without_divisions(),
        division_bridge_quarters=fx.divided(
            bridge=("linear", 0.001), second=0.003, end=0.005, injection=1e-12
        ),
        division_furrow=fx.cleft_divided(
            f=0.75, area_fraction=0.6, carriers=carriers, bridge=("linear", 0.001)
        ),
        division_quartered=quartered,
        division_quartered_values=revalued(quartered),
    )


def selected(names=()):
    """division_worlds(), restricted to names when any are given."""
    worlds = division_worlds()
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
    """§8.4's promise on saved outputs (module docstring). Writes check.json; True when it holds."""
    directory = Path(directory)
    report, ok = {"worlds": {}, "twins": {}}, True
    saved = {path.stem: np.load(path) for path in sorted(directory.glob("*.npz"))}
    for name in division_worlds():
        if name not in saved:
            report["worlds"][name] = "MISSING bindings"
            ok = False
            continue
        arrays, closed, entry = saved[name], _closed(directory, name), {}
        for key in BOUND:
            if key not in arrays.files:
                entry[key], ok = "MISSING from the bindings", False
            elif not np.any(arrays[key]):
                entry[key] = "bound; all zero, so not distinguishable from a constant by digest"
            elif _digest(arrays[key]) in closed:
                entry[key], ok = "COINCIDES with a closed-over constant", False
            else:
                entry[key] = "bound; no closed-over constant equals it"
        report["worlds"][name] = entry
    for twin, (original, moved) in TWINS.items():
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
        unmoved = [k for k in moved if k not in differ]
        holds = all(texts.values()) and all(consts.values()) and not unmoved
        ok &= holds
        report["twins"][twin] = dict(
            original=original,
            texts_identical=texts,
            constants_identical=consts,
            bindings_that_differ=differ,
            references_that_did_not_move=unmoved,
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
