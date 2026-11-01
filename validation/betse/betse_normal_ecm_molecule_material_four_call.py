"""Held one-sequence standalone material four-call/source qualification.

Declared manufactured material inputs are never INIT/phase/native-world owner
authority. This composes the existing primitive, legacy source, original BETSE
compiler and Decimal providers; it implements no transport equation.
"""

import argparse
import copy
import hashlib
import json
import sys
from collections import Counter
from decimal import Decimal
from pathlib import Path
from types import MethodType

import numpy as np

from cells.processes import betse_normal_ecm_molecule_material_primitive as primitive
from validation import source_snapshot as snapshot
from validation.betse import betse_ecm_transport_checks as checks
from validation.betse import betse_ecm_transport_fixtures as fixtures
from validation.betse import betse_normal_ecm_molecule_material_four_call_reference as reference
from validation.betse import betse_normal_ecm_molecule_material_primitive as primitive_validation
from validation.betse.betse_normal_channel_join_runtime import inventory
from validation.betse.betse_normal_ecm_molecule_handoff_run_plugin import Calls, identity

KIND = "cells.standalone_material_four_call_qualification@1"
FILE = "validation/betse/betse_normal_ecm_molecule_material_four_call.py"
OWNED = (
    FILE,
    "validation/betse/betse_normal_ecm_molecule_material_four_call_reference.py",
    "tests/unit/test_betse_normal_ecm_molecule_material_four_call.py",
    "tests/unit/test_betse_normal_ecm_molecule_material_four_call_reference.py",
)
FIXTURE_SHA256 = "477690ed585be18b1f87351027bd2ff481606ce612ea31029f5c7bc846339ac2"
CHECKS_SHA256 = "c3bd2290e18f5a565af8694c6e7f5af08a14406e2b13ba9593a90e987d0b6122"
require = primitive.require


def program():
    """Original slow initial/first-three inputs plus one explicit fourth packet."""
    require(snapshot.digest(Path(fixtures.__file__)) == FIXTURE_SHA256, "Original fixture changed")
    value = fixtures.fixture("slow")
    require(len(value["steps"]) == 3, "Original three-call slow fixture required")
    fourth = copy.deepcopy(value["steps"][2])
    fourth["junction_block"] = [0.79] * 9
    fourth["boundary_mol_m3"] = [23.15, 26.15, 29.15, 32.15]
    value["steps"].append(fourth)
    return value


def validate_program(value):
    require(
        type(value) is dict
        and set(value) == {"definition", "initial", "steps"}
        and type(value["steps"]) is list
        and len(value["steps"]) == 4,
        "Complete declared four-call material inputs required",
    )
    require(
        primitive.codec.fingerprint(value) == primitive.codec.fingerprint(program()),
        "Foreign/modified four-call initial state or forcing; no fixture fallback",
    )
    require(len({id(v) for v in value["steps"]}) == 4, "Distinct ordered packet objects required")


def declared_domain():
    return primitive.declare(
        primitive.contract.budget(
            source_calls=4,
            max_material_attempts=4,
            max_owner_verifications=20,
            max_nested_source_invocations=1_000_000,
            max_retained_bytes=32 * 2**20,
            wall_seconds=480.0,
            provenance="Declared original slow material fixture plus explicit packet4; unqualified",
        ),
        run_id="standalone-slow-explicit-four",
        provenance="One declared manufactured sequence; no native initialization authority",
    )


def ref(path):
    path = Path(path).resolve(strict=True)
    return dict(path=str(path), sha256=snapshot.digest(path))


def source_plan():
    _, adapter = reference.adapter_ast()
    require(
        snapshot.digest(Path(checks.__file__)) == CHECKS_SHA256,
        "Existing comparison budgets changed",
    )
    protocol = json.loads(reference.native.PROTOCOL.read_text())
    pins = protocol["native_source"]
    root = Path(pins["checkout"])
    for name, expected in pins["source_sha256"].items():
        require(
            snapshot.digest(root / name) == expected,
            "Changed pinned original BETSE source: " + name,
        )

    def source_ref(path):
        path = Path(path).resolve()
        return dict(
            checkout_path=str(path.relative_to(Path(__file__).resolve().parents[2])),
            sha256=snapshot.digest(path),
        )

    return dict(
        adapter=adapter,
        native_source=pins,
        fixture=source_ref(fixtures.__file__),
        comparison=source_ref(checks.__file__),
        native_protocol=source_ref(reference.native.PROTOCOL),
        historical_failed_parent=protocol["known_failed_case"],
        original_failed_case_not_repaired=True,
        existing_tolerances=protocol["tolerances"],
        old_max_source_calls=3,
        new_declared_source_calls=4,
        independent_input_sequences=1,
        independent_biological_cases=0,
        actual_work=dict(
            primitive_material=4,
            legacy_prefix_replay=3,
            original_BETSE_material=4,
            Decimal100=4,
            Decimal160=4,
        ),
        claims=dict(
            source_correspondence="conditional, pending released execution",
            declared_initial_values_are_INIT_authority=False,
            coupled_or_checkpoint_admission=False,
        ),
    )


def data(value):
    """Exact Decimal evidence encoding, not an executable/general object codec."""
    if type(value) is Decimal:
        return ("exact_Decimal", str(value))
    if type(value) is dict:
        return {k: data(v) for k, v in value.items()}
    if type(value) in (tuple, list):
        return type(value)(data(v) for v in value)
    return value


class EvidenceEncoder(primitive.codec.Encoder):
    """Detached numeric observations, never writable-view checkpoint authority.

    The unchanged codec writes owned copies. Original layouts, repeated array
    identities and complete ndarray/byte-buffer bases remain separate evidence;
    decoding does not reconstruct their live alias relationships.
    """

    def __init__(self, limits=primitive.codec.DEFAULT_LIMITS):
        super().__init__(limits)
        self.observations, self.originals, self.snapshots = [], {}, set()
        self.storage_bounds = {}
        self.observed_bytes = 0

    def _observe(self, value, depth):
        require(depth <= self.limits.depth, "Evidence array base depth bound")
        if id(value) in self.originals:
            original, index, copied = self.originals[id(value)]
            require(original is value and copied is not None, "Changed or cyclic array identity")
            return index, copied
        require(len(self.observations) < self.limits.arrays, "Evidence array count bound")
        kind = type(value)
        require(kind in (np.ndarray, bytes, bytearray), "Unsupported evidence array base")
        array = value if kind is np.ndarray else np.frombuffer(value, dtype=np.uint8)
        require(
            array.dtype.kind in "biuf"
            and array.dtype.itemsize in (1, 2, 4, 8)
            and array.dtype.metadata is None,
            "Unsupported evidence array dtype",
        )
        require(
            array.ndim <= self.limits.dimensions and array.size <= self.limits.elements,
            "Evidence array shape bound",
        )
        self.observed_bytes += array.nbytes
        require(self.observed_bytes <= self.limits.expanded_bytes, "Evidence numeric byte bound")
        index = len(self.observations)
        self.originals[id(value)] = (value, index, None)
        row = dict(
            category="ndarray" if kind is np.ndarray else kind.__name__,
            dtype=array.dtype.str,
            shape=list(array.shape),
            strides=list(array.strides),
            writable=bool(array.flags.writeable),
            owns_data=bool(array.flags.owndata),
            aligned=bool(array.flags.aligned),
            C=bool(array.flags.c_contiguous),
            F=bool(array.flags.f_contiguous),
            base=None,
            offset_bytes=None,
            logical_snapshot=None,
        )
        self.observations.append(row)
        if kind is np.ndarray and value.base is not None:
            base, _ = self._observe(value.base, depth + 1)
            original_base = value.base
            storage = (
                original_base
                if type(original_base) is np.ndarray
                else np.frombuffer(original_base, dtype=np.uint8)
            )
            row.update(
                base=base,
                offset_bytes=int(
                    array.__array_interface__["data"][0] - storage.__array_interface__["data"][0]
                ),
            )
            bounds = self.storage_bounds[id(original_base)]
        else:
            require(
                kind is not np.ndarray
                or (array.flags.owndata and (array.flags.c_contiguous or array.flags.f_contiguous)),
                "Unsupported evidence owning storage",
            )
            address = array.__array_interface__["data"][0]
            bounds = address, address + array.nbytes
        address = array.__array_interface__["data"][0]
        lower = address + sum(
            min(0, (n - 1) * s) for n, s in zip(array.shape, array.strides, strict=True)
        )
        upper = address + sum(
            max(0, (n - 1) * s) for n, s in zip(array.shape, array.strides, strict=True)
        )
        upper += array.itemsize
        if array.size == 0:
            lower = upper = address
        require(bounds[0] <= lower <= upper <= bounds[1], "Evidence view exceeds source storage")
        self.storage_bounds[id(value)] = bounds
        # No data read from this view precedes complete base-chain/bounds checks.
        copied = np.array(array, copy=True, order="F" if array.flags.f_contiguous else "C")
        self.originals[id(value)] = (value, index, copied)
        self.snapshots.add(id(copied))
        row["logical_snapshot"] = copied
        require(
            array.tobytes(order="C") == copied.tobytes(order="C"),
            "Array changed during evidence capture",
        )
        return index, copied

    def encode(self, value, depth=0):
        if type(value) is np.ndarray and id(value) not in self.snapshots:
            _, value = self._observe(value, depth)
        return super().encode(value, depth)

    def capture(self, value):
        return super().capture(dict(payload=value, array_observations=self.observations))


def archive(directory, value):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=False)
    encoder = EvidenceEncoder()
    tree = encoder.capture(data(value))
    encoder.write(directory, tree)
    snapshot.write_json(
        directory / "manifest.json",
        dict(
            kind="cells.material_four_call_evidence@2",
            fingerprint=encoder.seal(tree),
            files={name: ref(directory / name) for name in ("state.json", "arrays.npz")},
            owner_admission=False,
            live_array_aliases_reconstructed=False,
        ),
    )
    primitive.codec._sync_directory(directory)
    return directory


def read_archive(directory, *, with_array_observations=False):
    directory = Path(directory)
    row = primitive.codec.parse_json(
        primitive_validation.checkpoint._read(
            directory / "manifest.json", primitive.codec.DEFAULT_LIMITS.json_bytes
        ),
        primitive.codec.DEFAULT_LIMITS,
    )
    require(
        row.get("kind")
        in (
            "cells.material_four_call_evidence@1",
            "cells.material_four_call_evidence@2",
        )
        and row.get("owner_admission") is False,
        "Require data-only four-call evidence",
    )
    blobs = {}
    for name, limit in (
        ("state.json", primitive.codec.DEFAULT_LIMITS.json_bytes),
        ("arrays.npz", primitive.codec.DEFAULT_LIMITS.archive_bytes),
    ):
        require(
            Path(row["files"][name]["path"]) == (directory / name).resolve(), "Foreign archive file"
        )
        blob = primitive_validation.checkpoint._read(directory / name, limit)
        require(
            hashlib.sha256(blob).hexdigest() == row["files"][name]["sha256"],
            "Changed evidence bytes",
        )
        blobs[name] = blob
    value = primitive.codec.decode(
        primitive.codec.parse_json(blobs["state.json"], primitive.codec.DEFAULT_LIMITS),
        blobs["arrays.npz"],
    )
    require(
        primitive.codec.fingerprint(value) == row["fingerprint"], "Changed four-call evidence graph"
    )
    if row["kind"] == "cells.material_four_call_evidence@2":
        require(
            type(value) is dict and set(value) == {"payload", "array_observations"},
            "Incomplete array observation envelope",
        )
        return (
            (value["payload"], value["array_observations"])
            if with_array_observations
            else value["payload"]
        )
    return (value, []) if with_array_observations else value


def partial(frame):
    """Explicit numerical-data projection; callback/native-object storage is closed."""
    local = frame.f_locals
    result = {
        k: copy.deepcopy(data(local[k]))
        for k in (
            "inputs",
            "history",
            "frames",
            "environment_records",
            "intermediate",
            "native_geometry",
            "before_rng",
            "after_rng",
            "v",
        )
        if k in local
    }
    omitted = {}
    for name in ("sim", "cells", "parameters"):
        if name not in local:
            continue
        values, skipped = {}, {}
        for key, value in vars(local[name]).items():
            if type(value) in (
                dict,
                list,
                tuple,
                str,
                int,
                float,
                bool,
                type(None),
                np.ndarray,
            ) or isinstance(value, np.generic):
                values[key] = copy.deepcopy(data(value))
            else:
                skipped[key] = dict(
                    type=type(value).__module__ + "." + type(value).__qualname__,
                    pinned_source_method=isinstance(value, MethodType),
                )
        result[name] = values
        omitted[name] = skipped
    return dict(
        available=result,
        omitted_nonnumerical_runtime_fields=omitted,
        projection="numerical data only; no native live-object/checkpoint claim",
    )


class Work(Calls):
    """Extend the existing observer with original/Decimal work and partials."""

    def __init__(self, stream):
        super().__init__(stream)
        self.reference_counts = Counter()
        self.indices = dict(primitive=[], legacy=[], native=[], Decimal100=[], Decimal160=[])
        self.partials, self.capture_errors = [], []

    def observe(self, frame, event, arg):
        module, name = frame.f_globals.get("__name__", ""), frame.f_code.co_name
        if (
            event == "return"
            and arg is None
            and name == "evaluate"
            and module in {reference.native.__name__, reference.decimal.__name__}
        ):
            try:
                self.partials.append(
                    dict(stage=self.stage, return_or_unwind=arg is None, **partial(frame))
                )
            except BaseException as error:
                self.capture_errors.append(
                    dict(stage=self.stage, type=type(error).__name__, message=str(error))
                )
        super().observe(frame, event, arg)
        if event != "call":
            return
        filename = frame.f_code.co_filename
        original = filename.startswith("<pinned native ") or filename == reference.PREFIX
        independent = module in {
            reference.native.__name__,
            reference.native.geometry_native.__name__,
            reference.decimal.__name__,
            "validation.betse.betse_environment_field_reference",
            "validation.betse.betse_normal_current_reference",
        }
        if original or independent:
            self.reference_counts[(module or filename) + "." + name] += 1
        boundary = None
        if frame.f_code is primitive._SOURCE_CODE:
            key = "primitive" if self.stage.startswith("primitive") else "legacy"
            index = frame.f_locals["parent"].step_index
            self.indices[key].append(index)
            boundary = key
        elif name == "observe" and frame.f_locals.get("stage") == "initial":
            caller = frame.f_back
            if (
                module == reference.native.__name__
                and caller.f_code.co_filename == reference.PREFIX
            ):
                self.indices["native"].append(caller.f_locals["index"])
                boundary = "native"
            elif module == reference.decimal.__name__:
                raw = caller.f_locals["packet_raw"]
                hits = [
                    i
                    for i, packet in enumerate(caller.f_locals["inputs"]["steps"])
                    if packet is raw
                ]
                require(len(hits) == 1, "Ambiguous Decimal input packet epoch")
                key = "Decimal100" if caller.f_locals["refinement"] == 1 else "Decimal160"
                self.indices[key].append(hits[0])
                boundary = key
        if boundary is not None or (independent and name in {"evaluate", "capture"}):
            self.sequence += 1
            entry = dict(
                event="entry",
                invocation=self.sequence,
                function=(module or filename) + "." + name,
                category="independent_source_boundary"
                if boundary is None
                else boundary + "_material_boundary",
                parent_invocation=None,
                pytest_stage=self.stage,
                phase=None,
            )
            self.active[id(frame)] = entry
            self.emit(entry)

    def stop(self):
        result = super().stop()
        result.update(
            reference_counts=dict(self.reference_counts),
            absolute_indices=self.indices,
            capture_errors=self.capture_errors,
            source_partial_count=len(self.partials),
            independent_input_sequences=1,
            independent_biological_cases=0,
        )
        return result


def compare_histories(rows, legacy, native, first, second, binding):
    require(
        len(rows) == len(native["history"]) == len(first["history"]) == len(second["history"]) == 4
        and len(legacy) == 3,
        "Complete four-call histories and original first-three replay required",
    )
    require(
        native["failure"] is None and not native["warnings"] and native["RNG_unchanged"] is True,
        "Original source failed/warned or changed RNG state",
    )
    require(
        native["native_source_sha256"] == source_plan()["native_source"]["source_sha256"],
        "Wrong original source identities",
    )
    geometry = binding.source.geometry_binding.geometry._asdict()
    checks.geometry_compare(geometry, native["geometry"])
    summaries = []
    for index, trial in enumerate(rows):
        original, coarse, fine = (
            native["history"][index],
            first["history"][index],
            second["history"][index],
        )
        require(
            original["source_completed"] is True and trial.candidate.step_index == index + 1,
            "Failed/duplicate/omitted source advance",
        )
        require(
            checks.metadata(trial) == checks.metadata(original) == checks.metadata(coarse),
            "Changed source order/ion metadata",
        )
        actual, source = (
            checks.columns(trial, ledgers=False),
            checks.columns(original, ledgers=False),
        )
        checks.compare(actual, source, exact=True)
        byte_matches = {
            key: (
                np.asarray(actual[key]).dtype == np.asarray(source[key]).dtype
                and np.asarray(actual[key]).shape == np.asarray(source[key]).shape
                and np.asarray(actual[key]).tobytes() == np.asarray(source[key]).tobytes()
            )
            for key in actual
        }
        agreement = checks.compare(checks.columns(trial), checks.columns(coarse))
        resolution = checks.compare(checks.columns(coarse), checks.columns(fine))
        require(resolution <= 0.1, "Existing Decimal resolution fraction exceeded")
        if index < 3:
            checks.compare(checks.columns(trial), checks.columns(legacy[index]), exact=True)
            require(
                trial.candidate.identity == legacy[index].candidate.identity,
                "Original first-three identity behavior changed",
            )
        for oracle in coarse["conservative_exchange"]:
            require(
                abs(oracle["balance_residual_mol"]) <= 1e-85,
                "Existing conservative oracle residual exceeded",
            )
            at = binding.source.geometry_binding.current_binding.ion_ids.index(oracle["ion_id"])
            frame = next(
                f
                for f in trial.frames
                if f.stage == "membrane_commit" and f.ion_id == oracle["ion_id"]
            )
            checks.compare(
                {"oracle.cell_mol_m3": frame.values.cell_mol_m3[at]},
                {"oracle.cell_mol_m3": oracle["cell_mol_m3"]},
            )
            checks.compare(
                {"oracle.environment_mol_m3": frame.values.environment_mol_m3[at]},
                {"oracle.environment_mol_m3": oracle["environment_mol_m3"]},
            )
        require(trial.diagnostics["finite"] is True, "Nonfinite primitive source trial")
        summaries.append(
            dict(
                absolute_index=index,
                parent_identity=trial.parent_identity,
                candidate_identity=trial.candidate.identity,
                source_value_exact=True,
                byte_agreement=all(byte_matches.values()),
                byte_mismatches=[k for k, same in byte_matches.items() if not same],
                independent_error_fraction=agreement,
                reference_resolution_fraction=resolution,
                diagnostics=dict(
                    finite=trial.diagnostics["finite"],
                    minimum_cell_mol_m3=float(np.min(trial.candidate.values.cell_mol_m3)),
                    minimum_environment_mol_m3=float(
                        np.min(trial.candidate.values.environment_mol_m3)
                    ),
                    minimum_membrane_mol_m3=float(np.min(trial.candidate.values.membrane_mol_m3)),
                    conservation_ledgers={k: trial.diagnostics[k] for k in checks.LEDGERS},
                ),
            )
        )
    return summaries


class EvidenceRejected(RuntimeError):
    def __init__(self, stage, returned):
        super().__init__("Four-call evidence refused after source return: " + stage)
        self.stage, self.returned = stage, returned


def check_work(accounting):
    require(
        accounting["profile_intact"]
        and accounting["active_invocations"] == 0
        and not accounting["capture_errors"],
        "Incomplete work observer",
    )
    require(
        accounting["absolute_indices"]
        == dict(
            primitive=[0, 1, 2, 3],
            legacy=[0, 1, 2],
            native=[0, 1, 2, 3],
            Decimal100=[0, 1, 2, 3],
            Decimal160=[0, 1, 2, 3],
        ),
        "Missing/duplicate/rebased actual work",
    )


def prepare(repository, directory):
    repo, directory = Path(repository).resolve(strict=True), Path(directory).resolve()
    require(
        Path(__file__).resolve() == repo / FILE
        and not directory.is_relative_to(repo)
        and not repo.is_relative_to(directory),
        "Current checkout and separate output required",
    )
    directory.mkdir(parents=True, exist_ok=False)
    value, plan = program(), source_plan()
    names = set(OWNED) | {"pyproject.toml", "tests/__init__.py"}
    for name, module in tuple(sys.modules.items()):
        if name.startswith(("cells", "validation")) and getattr(module, "__file__", None):
            path = Path(module.__file__).resolve()
            require(path.is_relative_to(repo), "Foreign loaded source regime")
            names.add(str(path.relative_to(repo)))
    names.update(
        str(p.resolve().relative_to(repo))
        for p in (reference.native.PROTOCOL, reference.native.geometry_native.PROTOCOL)
    )
    producer = primitive_validation.checkpoint.producer_identity()
    names.update("src/cells/" + n for n in producer["source_hashes"])
    manifest = snapshot.freeze(repo, directory / "source", {n: n for n in names})
    archive(directory / "program", value)
    snapshot.write_json(directory / "source-plan.json", plan)
    snapshot.write_json(
        directory / "inputs.json",
        dict(
            kind=KIND,
            held=True,
            automatic_launch=False,
            snapshot_sha256=snapshot.digest(directory / "source/SNAPSHOT.json"),
            program=ref(directory / "program/manifest.json"),
            source_plan=ref(directory / "source-plan.json"),
            expected_producer=producer,
            repository=str(repo),
            domain=primitive.domain_record(declared_domain()),
            release_gates=list(reference.RELEASES),
            resources=dict(
                cpu=0,
                threads=1,
                max_process_tree_bytes=2**30,
                wall_seconds=480,
                min_available_bytes=8 * 2**30,
            ),
            independent_input_sequences=1,
            independent_biological_cases=0,
            remaining=[
                "Root source/reader/runtime review",
                "Root release and guarded resource plan",
            ],
            no_INIT_or_coupled_or_checkpoint_admission=True,
        ),
    )
    return dict(
        snapshot=ref(directory / "source/SNAPSHOT.json"),
        inputs=ref(directory / "inputs.json"),
        files=len(manifest["files"]),
        held=True,
    )


def packet_inputs(packet, packet_sha256):
    """Metadata-only source/input checks; never positive owner admission."""
    packet = Path(packet).resolve(strict=True)
    require(snapshot.digest(packet / "inputs.json") == packet_sha256, "Wrong held packet")

    def read_json(path):
        return primitive.codec.parse_json(
            primitive_validation.checkpoint._read(path, primitive.codec.DEFAULT_LIMITS.json_bytes),
            primitive.codec.DEFAULT_LIMITS,
        )

    inputs = read_json(packet / "inputs.json")
    require(
        inputs["kind"] == KIND and inputs["held"] is True and inputs["automatic_launch"] is False,
        "Wrong qualification route",
    )
    snapshot.verify(packet / "source", manifest_sha256=inputs["snapshot_sha256"])
    require(Path(__file__).resolve() == packet / "source" / FILE, "Run exact prepared Git source")
    require(
        primitive_validation.checkpoint.producer_identity() == inputs["expected_producer"],
        "Changed producer/runtime",
    )
    require(
        ref(packet / "program/manifest.json") == inputs["program"], "Changed declared input graph"
    )
    for name in ("source_plan",):
        require(
            ref(packet / (name.replace("_", "-") + ".json")) == inputs[name],
            "Changed declared input/source plan",
        )
    value = read_archive(packet / "program")
    validate_program(value)
    require(read_json(packet / "source-plan.json") == source_plan(), "Source/context drift")
    require(
        primitive.domain_record(declared_domain()) == _tuples(inputs["domain"]),
        "Changed four-call domain",
    )
    return value, inputs


def worker(directory, *, packet, packet_sha256, enabled=False):
    reference.released(enabled)
    require(__debug__ and sys.flags.optimize == 0, "Assertion-enabled source comparisons required")
    value, inputs = packet_inputs(packet, packet_sha256)
    packet = Path(packet).resolve(strict=True)
    directory = Path(directory).resolve()
    for origin in (
        packet,
        Path(inputs["repository"]).resolve(),
        Path(source_plan()["native_source"]["checkout"]).resolve(),
    ):
        require(
            not directory.is_relative_to(origin) and not origin.is_relative_to(directory),
            "Output cannot modify held packet/source",
        )
    directory.mkdir(parents=True, exist_ok=False)
    available, errors, work = dict(inputs=value), [], None

    def take(name, action, projection=lambda v: v):
        work.stage = name
        try:
            result = action()
        except BaseException as primary:
            try:
                if type(primary) is primitive.PrimitiveRejected:
                    available["failed_primitive"] = primitive_validation.evidence(
                        primary.execution, primary
                    )
                available["source_exception_owned_fields"] = {
                    key: getattr(primary, key)
                    for key in ("partial", "parent", "drive", "trial")
                    if hasattr(primary, key)
                }
                archive(
                    directory / name,
                    dict(
                        status="failed",
                        failure=primitive_validation.checkpoint._exception_record(primary),
                        available=available,
                        source_partials=work.partials,
                        capture_errors=work.capture_errors,
                    ),
                )
            except BaseException as secondary:
                errors.append(
                    dict(stage=name, type=type(secondary).__name__, message=str(secondary))
                )
                primary.add_note("Four-call failure evidence also failed: " + repr(secondary))
            raise
        try:
            observed = projection(result)
            available["last_returned"] = observed
            archive(directory / name, dict(status="returned", returned=observed))
        except BaseException as secondary:
            raise EvidenceRejected(name, result) from secondary
        return result

    with (directory / "invocations.jsonl").open("x") as stream:
        work = Work(stream)
        work.start()
        try:
            execution = take(
                "primitive-begin",
                lambda: primitive.begin(declared_domain(), value["definition"], value["initial"]),
                lambda e: primitive_validation.evidence(e),
            )
            available["primitive"] = primitive_validation.evidence(execution)
            rows = []
            for index, raw in enumerate(value["steps"]):
                forcing = take(
                    "primitive-drive-" + str(index),
                    lambda raw=raw: primitive.material.drive(execution.binding.source, raw),
                )
                state, trial = take(
                    "primitive-step-" + str(index),
                    lambda forcing=forcing: execution.advance(execution.current, forcing),
                    lambda pair: (primitive.state_record(pair[0]), pair[1]),
                )
                require(state.absolute_index == index + 1, "Primitive absolute epoch reset/rebase")
                rows.append(trial)
                available["primitive"] = primitive_validation.evidence(execution)
            legacy_binding = take(
                "legacy-binding", lambda: primitive.material.bind(value["definition"])
            )
            parent = take(
                "legacy-initial", lambda: primitive.material.state(legacy_binding, value["initial"])
            )
            legacy = []
            for index, raw in enumerate(value["steps"][:3]):
                forcing = take(
                    "legacy-drive-" + str(index),
                    lambda raw=raw: primitive.material.drive(legacy_binding, raw),
                )
                trial = take(
                    "legacy-step-" + str(index),
                    lambda parent=parent, forcing=forcing: primitive.material.step(
                        legacy_binding, parent, forcing
                    ),
                )
                legacy.append(trial)
                parent = trial.candidate
                available["legacy"] = tuple(legacy)
            native = take("original-four", lambda: reference.evaluate_original(value, enabled=True))
            available["native"] = native
            exact = {}

            def keep_decimal(refinement, result):
                exact[refinement] = data(result)
                archive(
                    directory / ("Decimal-raw-" + str(refinement)),
                    dict(refinement=refinement, exact=exact[refinement]),
                )

            first = take(
                "Decimal100",
                lambda: reference.evaluate_decimal(
                    value, refinement=1, enabled=True, retain_decimal=lambda r: keep_decimal(1, r)
                ),
            )
            available["Decimal100"] = first
            second = take(
                "Decimal160",
                lambda: reference.evaluate_decimal(
                    value, refinement=2, enabled=True, retain_decimal=lambda r: keep_decimal(2, r)
                ),
            )
            available["Decimal160"] = second
            require(set(exact) == {1, 2}, "Complete raw Decimal coefficients required")
            require(
                not work.capture_errors,
                "Incomplete original/reference observation refuses comparison",
            )
            comparison = take(
                "comparison",
                lambda: compare_histories(rows, legacy, native, first, second, execution.binding),
            )
        except BaseException as primary:
            try:
                archive(
                    directory / "failure",
                    dict(
                        status="failed",
                        failure=primitive_validation.checkpoint._exception_record(primary),
                        available=available,
                        source_partials=work.partials,
                        capture_errors=work.capture_errors,
                        evidence_errors=errors,
                    ),
                )
            except BaseException as secondary:
                primary.add_note("Final four-call failure evidence also failed: " + repr(secondary))
            raise
        finally:
            primary = sys.exception()
            try:
                accounting = work.stop()
                snapshot.write_json(directory / "work.json", accounting)
                snapshot.write_json(
                    directory / "runtime.json", dict(child=identity(), loaded=inventory())
                )
            except BaseException as secondary:
                if primary is None:
                    raise
                primary.add_note("Four-call accounting evidence also failed: " + repr(secondary))
    check_work(accounting)
    archive(directory / "comparison-final", dict(per_step=comparison, work=accounting))
    snapshot.write_json(
        directory / "result.json",
        dict(
            status="conditional_standalone_four_call_comparison_passed",
            packet=ref(packet / "inputs.json"),
            comparison=ref(directory / "comparison-final/manifest.json"),
            work=ref(directory / "work.json"),
            independent_input_sequences=1,
            independent_biological_cases=0,
            physical_or_coupled_or_checkpoint_admission=False,
        ),
    )
    return comparison


def _tuples(value):
    return tuple(_tuples(v) for v in value) if type(value) is list else value


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--released", action="store_true")
    parser.add_argument("--packet", type=Path, required=True)
    parser.add_argument("--packet-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    require(args.worker, "Only explicit Root worker mode exists; no automatic launch")
    worker(args.output, packet=args.packet, packet_sha256=args.packet_sha256, enabled=args.released)


if __name__ == "__main__":
    main()
