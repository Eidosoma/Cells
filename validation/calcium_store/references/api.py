"""The references' outputs, as SPEC.md section 6 names them.

Each function returns plain numbers (doubles, each rounded once) in nested mappings and lists. A key's ending names its unit;
`units()` says the rest. By default a function reads `values.json` and runs nothing. With `compute=True` it makes the same
numbers again from `forms.py` and `world.py`.

`store_world(variant, control)`: the variant is "store_world" or "store_world_without_buffers". The control is None or one of
`controls()`: "release_sign", "pump_without_voltage", or "constants_one_percent: <a constant>", the constant as `inputs.json`
writes it.
"""

import functools
import json
import sys
from decimal import Decimal
from pathlib import Path

FOLDER = Path(__file__).resolve().parent
VALUES = FOLDER / "values.json"
INPUTS = FOLDER.parent / "reference_spec" / "inputs.json"

KERNEL_DIGITS = 60
BLOCK_DIGITS = 60

VARIANTS = ("store_world", "store_world_without_buffers")

UNITS = {
    "the rule": "a key's ending is its unit: _fmol, _V, _pJ, _s, _A, _per_s (1/s), _fmol_per_s, _pJ_per_s, _V_per_s, "
    "_fmol_per_s_per_V; it holds for everything inside that key",
    "no unit": "x and x_fuel (a free energy over RT), S, m, h, condition_factors, release_opening, in_domain",
    "cycles and extents": "one fmol of cycles, or of a reaction's extent, is 1 fmol",
    "signs": "a constant-field transfer is positive from the cell (inside) to the outside or the store; the release is "
    "positive from the store into the cell; pump and exchanger cycles and reaction extents are positive forward; "
    "J and the moves of a symport are positive for one inward cycle, from P to N; a heat is positive when it leaves "
    "the matter; a work is positive when the fuel supplies it",
    "eigenvalues_per_s": "five [real, imaginary] pairs by falling modulus; two are exactly zero (total Ca, total Na)",
    "jacobian_per_s": "row i, column j: d(rate of change of row i)/d(amount of row j), in the order of `rows`",
    "*_change*": "the value less its value at t = 0, a double of its own: a double of a large amount does not hold it",
}


@functools.lru_cache(maxsize=1)
def _values():
    return json.loads(VALUES.read_text(encoding="utf-8"))


@functools.lru_cache(maxsize=1)
def _inputs():
    return json.loads(INPUTS.read_text(encoding="utf-8"))


def _modules():
    """`forms` and `world`, imported only when something is computed."""
    if __package__:
        from . import forms, world
    else:
        if str(FOLDER) not in sys.path:
            sys.path.insert(0, str(FOLDER))
        import forms
        import world
    return forms, world


def plain(value):
    """Decimals as doubles, each rounded once (and no negative zero); mappings and sequences likewise."""
    if isinstance(value, dict):
        return {key: plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [plain(item) for item in value]
    if isinstance(value, Decimal):
        return float(value) if value != 0 else 0.0
    if value is None or isinstance(value, (bool, int, str)):
        return value
    raise TypeError(f"{value!r} is not a plain number")


def units():
    return dict(UNITS)


def controls():
    """The 17 names `store_world` takes as its control."""
    return [name for name in _values()["store_world"][VARIANTS[0]] if name != "none"]


def store_world(variant, control=None, *, compute=False):
    """The observables 1 to 4 of SPEC.md section 3 at each of `times_s`."""
    if not compute:
        return _values()["store_world"][variant]["none" if control is None else control]
    forms, world = _modules()
    with forms.working(world.SETTINGS["digits"]):
        model = world.StoreWorld(_inputs(), variant, control)
        times = model.times(_inputs())
        return plain(model.observables(times, model.solve(times)))


def initial_rates(variant, *, compute=False):
    """Every mover's rate and heat rate at t = 0, the two conditions' factors, and the voltages' rates of change."""
    if not compute:
        return _values()["initial_rates"][variant]
    forms, world = _modules()
    with forms.working(KERNEL_DIGITS):
        return plain(world.StoreWorld(_inputs(), variant).initial_rates())


def material_block(variant, time, *, compute=False):
    """The 5 x 5 block of SPEC.md section 3 at a time: the stored ones are t = 0 and the last of `times_s`."""
    if not compute:
        return _values()["material_block"][variant][repr(float(time))]
    forms, world = _modules()
    with forms.working(world.SETTINGS["digits"]):
        model = world.StoreWorld(_inputs(), variant)
        listed = model.times(_inputs())
        time = forms.exact(time)
        if time == 0:
            state = model.initial_unknowns()
        else:
            state = model.solve([t for t in listed if t < time] + [time])[-1]
    with forms.working(BLOCK_DIGITS):
        return plain(world.StoreWorld(_inputs(), variant).material_block(state))


def pump_states(*, compute=False):
    """Every output of SPEC.md section 5 for each of `pump_states`, in the order of the inputs."""
    if not compute:
        return _values()["pump_states"]
    forms, _world = _modules()
    with forms.working(KERNEL_DIGITS):
        return [{"tag": s["tag"], **plain(forms.pump_outputs(s))} for s in _inputs()["pump_states"]]


def exchanger_states(*, compute=False):
    """Every output of SPEC.md section 5 for each of `exchanger_states`, in the order of the inputs."""
    if not compute:
        return _values()["exchanger_states"]
    forms, _world = _modules()
    with forms.working(KERNEL_DIGITS):
        return [{"tag": s["tag"], **plain(forms.exchanger_outputs(s))} for s in _inputs()["exchanger_states"]]


def symport_states(*, compute=False):
    """Every output of SPEC.md section 5 for each of `symport_states`, in the order of the inputs."""
    if not compute:
        return _values()["symport_states"]
    forms, _world = _modules()
    laws = _inputs()["symport_laws"]
    with forms.working(KERNEL_DIGITS):
        return [
            {"law": s["law"], "tag": s["tag"], **plain(forms.symport_outputs(s, laws[s["law"]]))}
            for s in _inputs()["symport_states"]
        ]
