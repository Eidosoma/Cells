"""Observation-only pre-SEED RNG witness for the genuine demo consumer.

No seed, draw, state replacement, model ownership or parity is issued here.
The independent reference keeps its own original constructor and wire codec.
"""

import ast
import hashlib
import importlib
import json
import os
import random
import sys
from contextlib import contextmanager
from pathlib import Path
from types import CodeType, FunctionType, ModuleType

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
COMMON_MODULE = "validation.betse.native_common_start_rng"
COMMON_FILE = "validation/betse/native_common_start_rng.py"
ORIGINAL = "validation/betse/native_init_terminal_reference.py"
COMMON_KIND = "cells.explicit_fresh_common_start_rng_program@1"
COMMON_DECLARATION = "cells.paired_common_start_preparation@1"
COMMON_EPOCH = "after_parameters_before_world_construction"
COMMON_RELEASE = "CELLS_COMMON_START_RNG_RELEASED"
COMMON_SHA256 = "b52c20c4ede1fc9afbcefd9f22e65626156852cae552a12c14837e65dd1b9eb4"
COMMON_REVIEW_SHA256 = "58e4090dfaf544435bd132b703e470d59d49381ade83ea25a7ab0fe3a919d72e"
COMMON_STEPS = (
    ("python_before", "python_get", None),
    ("numpy_before", "numpy_get", None),
    ("python_seed", "python_seed", "python_seed"),
    ("python_after", "python_get", None),
    ("numpy_seed", "numpy_seed", "numpy_seed"),
    ("numpy_after", "numpy_get", None),
    ("python_readback", "python_get", None),
    ("numpy_readback", "numpy_get", None),
)
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


def common_declaration(value):
    """Authenticate the opt-in metadata shape without loading an RNG producer."""
    require(
        type(value) is dict
        and set(value) == {"kind", "mode", "program", "program_identity", "provider"}
        and value["kind"] == COMMON_DECLARATION
        and type(value["mode"]) is str
        and value["mode"] in ("original", "disabled"),
        "Exact per-mode common-start declaration required",
    )
    doc = value["program"]
    require(type(doc) is dict, "Explicit common-start program required")
    require(
        type(doc.get("python_seed")) is int
        and 0 <= doc["python_seed"] < 2**256
        and type(doc.get("numpy_seed")) is int
        and 0 <= doc["numpy_seed"] < 2**32
        and pin(doc.get("input_identity"))
        and type(doc.get("consumer_sources")) is dict
        and set(doc["consumer_sources"]) == {"cells", "original"}
        and all(pin(item) for item in doc["consumer_sources"].values()),
        "Bounded seeds, complete input identity and both caller hashes required",
    )
    expected = dict(
        kind=COMMON_KIND,
        epoch=COMMON_EPOCH,
        python_seed=doc["python_seed"],
        python_seed_version=2,
        numpy_seed=doc["numpy_seed"],
        numpy_api="legacy global RandomState.seed",
        input_identity=doc["input_identity"],
        consumer_sources=doc["consumer_sources"],
        operations=[list(row) for row in COMMON_STEPS],
        draws=0,
        setstate_or_generator_replacement=False,
    )
    # Canonical JSON preserves exact scalar types at the saved-document boundary.
    require(
        seal(doc) == seal(expected) and value["program_identity"] == seal(expected),
        "Canonical common-start program changed",
    )
    require(
        value["provider"]
        == dict(file=COMMON_FILE, sha256=COMMON_SHA256, review_sha256=COMMON_REVIEW_SHA256),
        "Explicit accepted common-start producer/review required",
    )
    return value


def common_binding(plan, manifest):
    """Bind one declaration to its actual mode, inventory and immutable callers."""
    selected = common_declaration(plan["common_start"])
    initial = validate_declaration(plan["initial_rng_inputs"])
    doc = selected["program"]
    require(
        selected["mode"] == plan["flux_operator"]
        and doc["input_identity"] == initial["inventory_sha256"]
        and doc["consumer_sources"]
        == {
            role: manifest["files"][name]["sha256"]
            for role, name in (("cells", DEMO), ("original", ORIGINAL))
        }
        and COMMON_FILE in manifest["files"],
        "Common-start mode, whole input inventory or actual caller source changed",
    )
    if COMMON_SHA256 is not None:
        require(
            manifest["files"][COMMON_FILE]["sha256"] == COMMON_SHA256,
            "Common-start producer differs from accepted source",
        )
    return selected


def common_preflight(plan):
    require(
        pin(COMMON_SHA256) and pin(COMMON_REVIEW_SHA256),
        "Reviewed common-start producer remains held",
    )
    require(os.environ.get(COMMON_RELEASE) == "1", "Common-start input program remains held")
    manifest = snapshot.verify(ROOT, manifest_sha256=plan["snapshot_sha256"])
    common_binding(plan, manifest)


def common_api():
    """Check loaded callable bodies as well as the frozen file before declaring inputs."""
    require(
        pin(COMMON_SHA256) and pin(COMMON_REVIEW_SHA256),
        "Reviewed common-start producer remains held",
    )
    path = snapshot.regular_file(ROOT, COMMON_FILE)
    raw = path.read_bytes()
    require(hashlib.sha256(raw).hexdigest() == COMMON_SHA256, "Common-start source changed")
    api = importlib.import_module(COMMON_MODULE)
    require(
        type(api) is ModuleType
        and sys.modules.get(COMMON_MODULE) is api
        and Path(api.__file__).resolve() == path,
        "Actual frozen common-start module required",
    )
    codes = {
        c.co_name: c
        for c in compile(raw, str(path), "exec", dont_inherit=True).co_consts
        if type(c) is CodeType
    }
    for node in ast.parse(raw).body:
        if not isinstance(node, ast.FunctionDef):
            continue
        function = vars(api).get(node.name)
        if node.decorator_list:
            require(
                [ast.unparse(item) for item in node.decorator_list] == ["contextmanager"],
                "Exact common-start wrapper required",
            )
            body = getattr(function, "__wrapped__", None)
            require(type(body) is FunctionType, "Actual common-start body required")
            wrapped = contextmanager(body)
            require(
                function.__code__ is wrapped.__code__
                and function.__globals__ is wrapped.__globals__
                and len(function.__closure__) == 1
                and function.__closure__[0].cell_contents is body,
                "Common-start wrapper/delegate changed",
            )
            function = body
        defaults = tuple(ast.literal_eval(item) for item in node.args.defaults) or None
        keywords = {
            arg.arg: ast.literal_eval(item)
            for arg, item in zip(node.args.kwonlyargs, node.args.kw_defaults, strict=True)
            if item is not None
        } or None
        require(
            type(function) is FunctionType
            and function.__code__ == codes[node.name]
            and function.__globals__ is vars(api)
            and function.__closure__ is None
            and function.__defaults__ == defaults
            and function.__kwdefaults__ == keywords,
            "Common-start callable/code/default changed",
        )
    require(
        api.FILE == COMMON_FILE
        and api.KIND == COMMON_KIND
        and api.EPOCH == COMMON_EPOCH
        and api.STEPS == COMMON_STEPS,
        "Common-start public contract changed",
    )
    return api


def common_request(plan):
    common_preflight(plan)
    api = common_api()
    doc = plan["common_start"]["program"]
    program = api.declare(
        python_seed=doc["python_seed"],
        numpy_seed=doc["numpy_seed"],
        input_identity=doc["input_identity"],
        consumer_sources=doc["consumer_sources"],
    )
    require(
        api.program_document(program) == doc
        and program.identity == plan["common_start"]["program_identity"],
        "Actual common-start Program differs from the explicit declaration",
    )
    return api, program


def common_return(value, declaration):
    common_declaration(declaration)
    require(
        type(value) is dict
        and value.get("kind") == COMMON_KIND
        and value.get("status") == "completed"
        and value.get("role") == "cells"
        and value.get("epoch") == COMMON_EPOCH
        and seal(value.get("program")) == seal(declaration["program"])
        and value.get("program_identity") == declaration["program_identity"]
        and value.get("source", {}).get("helper") == COMMON_FILE
        and value.get("source", {}).get("helper_sha256") == COMMON_SHA256
        and value.get("operations") == [[row[0], "returned"] for row in COMMON_STEPS]
        and value.get("states_loaded") is False
        and value.get("generators_replaced") is False
        and value.get("biological_or_phase_admission") is False,
        "Complete actual common-start return required before ambient observation",
    )
    return value


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
    common = getattr(state, "common_start_declaration", None)
    if common is None:
        expected = [("parameters", "returned"), ("initial_rng", "attempted")]
        require(
            not any(name == "common_start_rng" for name, _ in names),
            "Undeclared common-start operation cannot gain observation authority",
        )
    else:
        common_return(state.common_start_raw_return, common)
        require(
            state.common_start_record is state.common_start_raw_return
            and state.common_start_capture is not None
            and state.common_start_capture["label"] == "common_start_rng"
            and state.common_start_capture["status"] == "saved"
            and common["mode"] == state.flux_operator,
            "Original common-start return and successful capture required",
        )
        expected = [
            ("parameters", "returned"),
            ("common_start_rng", "returned"),
            ("initial_rng", "attempted"),
        ]
    require(
        names[-len(expected) :] == expected and not any(name == "geometry" for name, _ in names),
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
