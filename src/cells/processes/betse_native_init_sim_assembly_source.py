"""Pinned original SIM construction boundary, compiled but never evaluated."""

from functools import lru_cache
from types import CodeType

from cells.processes import betse_native_init_retained_world_source as original
from cells.processes import betse_native_tissue_configuration_source as tissue

NATIVE = original.NATIVE
PINS = dict(original.PINS)
for _path in (
    "betse/science/tissue/tisprofile.py",
    "betse/science/tissue/picker/tispickcls.py",
    "betse/science/tissue/picker/tispickimage.py",
    "betse/science/math/cache/cachelyrvec.py",
    "betse/science/math/cache/cacheupscaled.py",
    "betse/science/math/cache/cachevecfld.py",
):
    PINS[_path] = tissue.SOURCE_PINS[_path]

METHODS = dict(original.SITES)
METHODS.update(
    report=("betse/science/sim.py", "Simulator", "sim_info_report"),
    run_core=("betse/science/sim.py", "Simulator", "run_sim_core"),
)
IMPORT_FILES = tuple(path for path in PINS if path != "betse/science/simrunner.py")


def _payload(path):
    actual = NATIVE / path
    payload = actual.read_bytes()
    if actual.is_symlink() or original.hashlib.sha256(payload).hexdigest() != PINS[path]:
        raise ValueError("Exact pinned original SIM assembly source required: " + path)
    return payload


@lru_cache(maxsize=32)
def _compiled(payload, filename):
    # Only immutable executable metadata is cached. Every caller first reads
    # and checks the actual source bytes again; no owner or runtime is cached.
    unit = compile(payload, filename, "exec", dont_inherit=True, optimize=0)
    result = []

    def collect(code):
        result.append((code.co_qualname, code))
        for item in code.co_consts:
            if type(item) is CodeType:
                collect(item)

    collect(unit)
    return tuple(result)


def code(role):
    if role not in METHODS:
        raise ValueError("Unknown original SIM assembly method")
    path, owner, name = METHODS[role]
    return dict(_compiled(_payload(path), str(NATIVE / path)))[owner + "." + name]


def import_sites():
    """Closed top-level method roster from the exact constructor files."""
    result = {}
    for path in IMPORT_FILES:
        for qualified, member in _compiled(_payload(path), str(NATIVE / path)):
            pieces = qualified.split(".")
            if len(pieces) == 2 and member.co_flags & 1 and not member.co_name.startswith("<"):
                key = tuple(pieces)
                if key in result and result[key] != path:
                    raise ValueError("Ambiguous native assembly class/method")
                result[key] = path
    return result


def import_code(owner, method):
    path = import_sites().get((owner, method))
    if path is None:
        raise ValueError("Unknown original constructor-import method")
    return dict(_compiled(_payload(path), str(NATIVE / path)))[owner + "." + method]


def source_plan():
    return dict(
        kind="original_completed_INIT_to_fresh_SIM_constructor_source@1",
        original_files=PINS,
        order=(
            "runner compatibility",
            "SimPhase(SIM,cells,current_p,sim,callbacks)",
            "sim.sim_info_report(phase)",
            "sim.run_sim_core(phase)",
        ),
        retained=("actual completed INIT sim", "actual completed INIT cells"),
        replaced_owner="sim.dyna only, by the actual fresh constructor's handler",
        fresh=("complete current Parameters before phase birth", "phase", "cache", "handler"),
        constructor_parameter_stores=(
            "_run_sim=True",
            "dt=sim_time_step",
            "resample=sim_time_sampling",
            "total_time=sim_time_total",
            "t_resample=resample/dt",
        ),
        compiled_only=True,
        native_pickle_loadSim_autoInit_or_full_caller_history=False,
        run_core_numerical_execution_held=True,
    )
