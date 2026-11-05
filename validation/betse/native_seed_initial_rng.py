"""Observation-only pre-SEED RNG witness for the genuine demo consumer.

No seed, draw, state replacement, model ownership or parity is issued here.
The independent reference keeps its own original constructor and wire codec.
"""

import hashlib
import json
import random
import sys
from pathlib import Path

from validation import source_snapshot as snapshot
from validation.betse import native_rng_runtime as rng_runtime
from validation.betse import native_seed_demo_input_profiles as profiles
from validation.betse import native_seed_demo_inputs as inputs

FILE = "validation/betse/native_seed_initial_rng.py"
DEMO = "validation/betse/native_seed_demo.py"
ROOT = Path(__file__).resolve().parents[2]
LEGACY_KIND = "cells.common_initial_rng_observation@1"
KIND = "cells.common_initial_rng_observation@2"
EPOCH = "pre_SEED_before_world_construction"
RNG_RUNTIME_MODULES = (
    "numpy",
    "numpy.random",
    "numpy.random.mtrand",
    "numpy.random._mt19937",
    "numpy.random.bit_generator",
    "random",
    "_random",
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def pin(value):
    return type(value) is str and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def seal(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def declaration(program):
    """Bind all original input files before parameter allocation creates paths."""
    profile = profiles.require_profile(program.get("input_profile", profiles.ORIGINAL))
    inventory = inputs.inventory(Path(program["root"]))
    require(
        inventory == profiles.inventory(inputs._source(), profile),
        "Complete selected input bundle required",
    )
    return dict(profile=profile, inventory=inventory, inventory_sha256=seal(inventory))


def validate_declaration(value):
    require(
        type(value) is dict and set(value) == {"profile", "inventory", "inventory_sha256"},
        "Exact initial input declaration required",
    )
    profiles.require_profile(value["profile"])
    require(
        type(value["inventory"]) is dict and set(value["inventory"]) == {"directories", "files"},
        "Complete input inventory required",
    )
    require(
        pin(value["inventory_sha256"]) and seal(value["inventory"]) == value["inventory_sha256"],
        "Initial input inventory digest changed",
    )
    return value


def input_binding(plan, state):
    selected = validate_declaration(plan["initial_rng_inputs"])
    packet = Path(plan["parameter_packet"]) / "inputs.json"
    require(
        not packet.is_symlink()
        and packet.stat().st_size <= 2**20
        and snapshot.digest(packet) == plan["parameter_sha256"],
        "Original parameter input declaration changed",
    )
    program = json.loads(packet.read_text())["program"]
    require(
        program["root"] == str(state.input_root)
        and program.get("input_profile", profiles.ORIGINAL) == selected["profile"],
        "Same actual input root/profile required",
    )
    actual = inputs.inventory(Path(state.input_root))
    expected = selected["inventory"]
    # Parameter construction legitimately creates these output directories.
    # Their existence is not a difference in the original input inventory.
    allowed = set(expected["directories"])
    root = Path(state.input_root)
    for name in program["directories"]:
        directory = Path(name)
        require(directory.is_relative_to(root), "Native output directory escaped inputs")
        while directory != root:
            allowed.add(str(directory.relative_to(root)))
            directory = directory.parent
    require(
        actual["files"] == expected["files"]
        and set(expected["directories"]) <= set(actual["directories"]) <= allowed,
        "Complete selected input bytes or directory roster changed",
    )
    require(
        type(plan["flux_operator"]) is str and plan["flux_operator"] in ("original", "disabled"),
        "Exact operator mode required",
    )
    return dict(
        input_inventory_sha256=selected["inventory_sha256"],
        mode=plan["flux_operator"],
        profile=selected["profile"],
    )


def read_states(state):
    observed = {}
    state.initial_rng_raw = observed  # Retain the first getter even if the second fails.
    observed["numpy_random"] = sys.modules["numpy"].random.get_state()
    observed["python_random"] = random.getstate()
    observed["initial_random_reset_or_replacement"] = False
    return observed


def runtime_binding():
    return rng_runtime.binding()


def validate_states(observed):
    import numpy as np

    require(
        type(observed) is dict
        and set(observed)
        == {"numpy_random", "python_random", "initial_random_reset_or_replacement"}
        and observed["initial_random_reset_or_replacement"] is False,
        "Complete observation-only RNG state required",
    )
    mt, py = observed["numpy_random"], observed["python_random"]
    require(
        type(mt) is tuple
        and len(mt) == 5
        and mt[0] == "MT19937"
        and type(mt[1]) is np.ndarray
        and mt[1].dtype.str in ("<u4", ">u4")
        and mt[1].shape == (624,)
        and mt[1].strides == (4,)
        and any(int(word) != 0 for word in mt[1])
        and type(mt[2]) is int
        and 0 <= mt[2] <= 624
        and type(mt[3]) is int
        and mt[3] in (0, 1)
        and type(mt[4]) is float,
        "Complete original NumPy MT state required",
    )
    require(
        type(py) is tuple
        and len(py) == 3
        and type(py[0]) is int
        and py[0] == 3
        and type(py[1]) is tuple
        and len(py[1]) == 625
        and all(type(word) is int and 0 <= word < 2**32 for word in py[1][:-1])
        and type(py[1][-1]) is int
        and 0 <= py[1][-1] <= 624
        and (py[2] is None or type(py[2]) is float),
        "Complete original Python MT state required",
    )


def validate_runtime(value):
    rng_runtime.validate(value)


def source_binding(plan):
    manifest_path = ROOT / "SNAPSHOT.json"
    require(
        not manifest_path.is_symlink()
        and snapshot.digest(manifest_path) == plan["snapshot_sha256"],
        "Original execution snapshot changed",
    )
    manifest = json.loads(manifest_path.read_text())
    files = {}
    for name in (FILE, DEMO, rng_runtime.FILE):
        path = snapshot.regular_file(ROOT, name)
        expected = manifest["files"][name]["sha256"]
        require(pin(expected) and snapshot.digest(path) == expected, "Initial RNG producer changed")
        files[name] = expected
    return dict(
        files=files,
        snapshot_sha256=plan["snapshot_sha256"],
        parameter_packet_sha256=plan["parameter_sha256"],
    )


def order_binding(state):
    require(
        state.parameters is not None
        and state.world_ready is not None
        and state.callback is not None
        and state.phase is None
        and state.seed_phase is None
        and state.init_phase is None
        and not state.owners
        and not state.trials
        and not state.requests,
        "Initial RNG observation requires fresh same-p pre-phase order",
    )
    require(
        state.world_ready.parameters is state.parameters,
        "Original WorldReady parameter association changed",
    )
    names = [(row["name"], row["status"]) for row in state.operations]
    require(
        names[-2:] == [("parameters", "returned"), ("initial_rng", "attempted")]
        and not any(name == "geometry" for name, _ in names),
        "Initial RNG observation must immediately precede geometry",
    )
    return dict(
        boundary="after_issued_WorldReady_before_geometry_phase_construction",
        parameter_identity=id(state.parameters),
        world_ready_identity=id(state.world_ready),
        callback_identity=id(state.callback),
        same_parameter=True,
        seed_entered=False,
        selected_boundaries=names,
    )


def save_observation(state, evidence, label, value):
    """Use the existing codec/writer, retaining raw errors before reporting them.

    Ordinary Evidence.save deliberately returns False after encoding an error.
    These two prerequisite captures must propagate that actual error instead.
    The rows and filenames keep the existing Evidence grammar.
    """
    from validation.betse import native_init_capture_budget as budget
    from validation.betse.native_single_cell_prefix_qualification import archive, exception_record

    row = dict(label=label, path=f"capture-{len(evidence.rows):04d}.json")
    state.initial_rng_capture_rows.append(row)
    try:
        budget.preflight(value)
        serialized = archive.snapshot(value)
        require(callable(evidence.capture_writer), "Original multipart observation writer required")
        evidence.capture_writer(label, evidence.output / row["path"], serialized)
        row.update(status="saved", sha256=snapshot.digest(evidence.output / row["path"]))
        evidence.rows.append(row)
    except BaseException as error:
        state.initial_rng_capture_error = error
        row["status"] = "capture_failed"
        try:
            row["error"] = exception_record(error)
        except BaseException as secondary:
            state.initial_rng_capture_secondary.append(secondary)
        try:
            if not any(previous is row for previous in evidence.rows):
                evidence.rows.append(row)
        except BaseException as secondary:
            state.initial_rng_capture_secondary.append(secondary)
        raise
    return True


def observe(state, plan, evidence):
    """Called once by the driver after its actual WorldReady/p identity check."""
    require(
        not state.initial_rng_attempted
        and state.initial_rng_raw is None
        and state.initial_rng_witness is None
        and state.initial_rng_observation is None,
        "Initial RNG capture is one-shot",
    )
    state.initial_rng_attempted = True
    order = order_binding(state)
    common = input_binding(plan, state)
    source = source_binding(plan)
    observed = read_states(state)
    validate_states(observed)
    runtime = runtime_binding()
    validate_runtime(runtime)
    witness = dict(
        kind=KIND,
        epoch=EPOCH,
        common_binding=dict(common, runtime=runtime),
        state=observed,
        source=source,
        order=order,
        observed_states_equalized=False,
        common_starting_authority_established=False,
        scientific_physical_checkpoint_credit=0,
    )
    state.initial_rng_witness = witness  # Before the first fallible writer.
    for label, raw in (("before_seed_random_states", observed), ("pre_seed_rng_witness", witness)):
        require(
            save_observation(state, evidence, label, raw),
            "Initial RNG evidence capture failed: " + label,
        )
        row = evidence.rows[-1]
        require(
            row.get("label") == label and row.get("status") == "saved" and pin(row.get("sha256")),
            "Actual completed initial RNG capture required",
        )
        if label == "pre_seed_rng_witness":
            state.initial_rng_observation = dict(row)
    return witness
