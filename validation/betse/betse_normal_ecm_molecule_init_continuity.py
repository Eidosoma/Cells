"""Held in-process acquisition of ordinary INIT and transport to continuity.

Only existing phase/run APIs create owners. A typed pre-setup declaration is
configuration transport, not positive phase authority. Completed owners remain
live objects; diagnostic archives/receipts are never loaded as an INIT parent.
The caller must provide genuine input provenance and the explicit SIM program.
"""

import json
import os
import sys
from pathlib import Path

from validation import source_snapshot as snapshot
from validation.betse import betse_normal_ecm_molecule_current_continuity as continuity
from validation.betse.betse_normal_channel_join_runtime import inventory
from validation.betse.betse_normal_ecm_init_phase_capture import record_failure
from validation.betse.betse_normal_ecm_molecule_handoff_run_plugin import Calls, identity

checkpoint, run, phase = continuity.checkpoint, continuity.run, continuity.lifecycle.init
retention, require = continuity.retention, continuity.require
FILE = "validation/betse/betse_normal_ecm_molecule_init_continuity.py"
OWNED = (FILE, "tests/unit/test_betse_normal_ecm_molecule_init_continuity.py")
KIND = "cells.in_process_molecule_INIT_continuity@1"
RELEASES = continuity.RELEASES


def parent_evidence(value):
    """Retain a refused path as data, never interpret it as a phase owner."""
    if isinstance(value, Path):
        return dict(
            refused_parent_type=type(value).__name__, path=str(value), owner_admission=False
        )
    return value


def preflight_declaration(declaration):
    """Refuse before setup; this structural check grants no owner admission."""
    require(
        type(declaration) is phase.Declaration, "Explicit typed pre-setup INIT declaration required"
    )
    calendar = declaration.calendar
    require(
        type(calendar) is run.calendars.NativePhaseCalendar
        and calendar.phase == "INIT"
        and type(calendar.step_count) is int
        and 0 <= calendar.step_count <= 3,
        "Require the complete original INIT calendar within the existing domain",
    )
    raw = declaration.inputs
    require(
        raw["kind"] == phase.INPUT_KIND
        and raw["time_profile"]["phase"] == "INIT"
        and raw["flags"]["phase"] == "INIT"
        and raw["flags"]["_run_sim"] is False
        and type(raw["stop_after_calls"]) is int
        and raw["stop_after_calls"] == calendar.step_count,
        "SIM/capped/incomplete declarations cannot acquire a completed INIT",
    )
    return dict(
        original_calls=calendar.step_count,
        declaration_identity=declaration.identity,
        owner_admission=False,
        actual_initialize_and_verification_still_required=True,
    )


def run_contract(template, binding=None):
    """Associate only the actual returned owner ID; no biological defaults."""
    require(type(template) is dict, "Explicit existing headless run contract required")
    require(
        set(template)
        == {
            "kind",
            "case_id",
            "run_id",
            "component_binding_identity",
            "time_profile",
            "entry_mode",
            "observation_mode",
            "stop_policy",
            "persistence",
        }
        and template["kind"] == run.INPUT_KIND,
        "Complete existing run contract required",
    )
    require(
        template["time_profile"]["phase"] == "INIT"
        and template["entry_mode"] == "supplied_molecule54_phase_entry"
        and template["observation_mode"] == "headless_only_native_display_refused"
        and template["stop_policy"] == "accepted_call_boundaries_only"
        and template["persistence"] == "none",
        "Original INIT clock/headless/native-persistence scope required",
    )
    require(
        all(
            type(template[name]) is str and bool(template[name].strip())
            for name in ("case_id", "run_id")
        ),
        "Root must explicitly declare the INIT run labels",
    )
    if binding is None:
        return template
    expected = template["component_binding_identity"]
    require(expected is None or expected == binding.identity, "Foreign explicit INIT run owner")
    return dict(template, component_binding_identity=binding.identity)


def write_graph(directory, value):
    directory = Path(directory)
    directory.mkdir(exist_ok=False)
    encoder = checkpoint.codec.Encoder()
    tree = encoder.capture(value)
    encoder.write(directory, tree)
    return dict(
        fingerprint=encoder.seal(tree),
        state=continuity.ref(directory / "state.json"),
        arrays=continuity.ref(directory / "arrays.npz"),
    )


def read_graph(directory, row):
    directory = Path(directory).resolve()
    require(
        continuity.pinned(row["state"]) == directory / "state.json"
        and continuity.pinned(row["arrays"]) == directory / "arrays.npz",
        "Foreign closed input graph",
    )
    limits = checkpoint.codec.DEFAULT_LIMITS
    tree = checkpoint.codec.parse_json(
        checkpoint._read(directory / "state.json", limits.json_bytes), limits
    )
    value = checkpoint.codec.decode(
        tree, checkpoint._read(directory / "arrays.npz", limits.archive_bytes)
    )
    require(checkpoint.codec.fingerprint(value) == row["fingerprint"], "Changed closed input graph")
    return value


def prepare(
    repository,
    directory,
    *,
    source_selection,
    source_selection_sha256,
    declaration=None,
    run_inputs=None,
    provenance=None,
    input_producer=None,
    input_evidence=(),
    retained_evidence=(),
    native_root=continuity.reference.native.ROOT,
):
    """Freeze source and explicit pre-setup inputs, without publishing a parent.

    inputs.json is reserved for a later exclusive publication using actual INIT
    identities. The source snapshot and acquisition-inputs.json never change.
    Missing biological/configuration authorities stay declared prerequisites.
    """
    repository = Path(repository).resolve(strict=True)
    require(Path(__file__).resolve() == repository / FILE, "Prepare from the current checkout")
    selection = Path(source_selection).resolve(strict=True)
    require(selection.name == "SNAPSHOT.json", "Snapshot source selection required")
    previous = snapshot.verify(selection.parent, manifest_sha256=source_selection_sha256)
    directory = continuity.output_path(directory, repository, selection.parent, native_root)
    directory.mkdir(parents=True, exist_ok=False)
    try:
        producer = checkpoint.producer_identity()
        files = {name: row["checkout_path"] for name, row in previous["files"].items()}
        require(all(name == path for name, path in files.items()), "No historical source overlay")
        files.update(continuity.source_files(repository))
        files.update({name: name for name in OWNED})
        files.update(
            {"src/cells/" + name: "src/cells/" + name for name in producer["source_hashes"]}
        )
        declared = preflight_declaration(declaration) if declaration is not None else None
        graph = write_graph(
            directory / "INIT-inputs", dict(declaration=declaration, run_inputs=run_inputs)
        )
        manifest = snapshot.freeze(repository, directory / "source", files)
        for name, digest in producer["source_hashes"].items():
            require(
                manifest["files"]["src/cells/" + name]["sha256"] == digest,
                "Changed producer during freeze",
            )
        snapshot.assert_checkout_unchanged(directory / "source")
        inputs = dict(
            kind=KIND,
            held=True,
            automatic_launch=False,
            release_gates=RELEASES,
            repository=str(repository),
            snapshot=continuity.ref(directory / "source/SNAPSHOT.json"),
            source_selection=continuity.ref(selection),
            expected_producer=producer,
            formatter_reference_source_plan=json.loads(
                json.dumps(continuity.reference.source_plan(native_root))
            ),
            native_root=str(Path(native_root).resolve()),
            INIT_inputs=graph,
            declared_INIT=declared,
            provenance=provenance,
            input_producer=input_producer,
            input_evidence=[continuity.ref(path) for path in input_evidence],
            retained_evidence=[continuity.ref(path) for path in retained_evidence],
            input_scope=(
                "explicit supplied typed declaration; not native geometry/Parameters derivation"
            ),
            external_input_binding_work=(
                "Root must retain its producer/accounting; not claimed as zero"
            ),
            continuation_publication=(
                "exclusive inputs.json after actual completed INIT and explicit SIM inputs"
            ),
            missing_prerequisites=[
                name
                for name, present in (
                    ("Root's genuine typed INIT declaration", declaration is not None),
                    ("explicit headless INIT run contract", run_inputs is not None),
                    (
                        "input provenance/source-work evidence",
                        bool(provenance) and bool(input_evidence) and input_producer == producer,
                    ),
                    ("explicit SIM declaration after actual INIT", False),
                    ("Root scientific release and resource selection", False),
                )
                if not present
            ],
            actual_entries=0,
            independent_biological_cases=0,
            native_derivation_attested=False,
        )
        snapshot.write_json(directory / "acquisition-inputs.json", inputs)
        return inputs
    except BaseException as error:
        record_failure(
            error,
            stage="prepare-in-process-INIT",
            readers={"source_selection": lambda: str(selection)},
            retain=lambda payload: snapshot.write_json(directory / "failure.json", payload),
        )
        raise


def verify_packet(packet, sha256):
    packet = Path(packet).resolve(strict=True)
    path = continuity.pinned(dict(path=str(packet / "acquisition-inputs.json"), sha256=sha256))
    inputs = checkpoint.codec.parse_json(
        checkpoint._read(path, checkpoint.codec.DEFAULT_LIMITS.json_bytes),
        checkpoint.codec.DEFAULT_LIMITS,
    )
    require(
        inputs["kind"] == KIND
        and inputs["held"] is True
        and inputs["automatic_launch"] is False
        and inputs["release_gates"] == list(RELEASES),
        "Changed held INIT acquisition route",
    )
    require(
        continuity.pinned(inputs["snapshot"]) == packet / "source/SNAPSHOT.json",
        "Foreign acquisition snapshot",
    )
    snapshot.verify(packet / "source", manifest_sha256=inputs["snapshot"]["sha256"])
    for row in (*inputs["input_evidence"], *inputs["retained_evidence"]):
        continuity.pinned(row)
    return inputs


def released():
    require(
        all(os.environ.get(name) == "1" for name in RELEASES),
        "Both existing Root releases required",
    )
    require(
        __debug__ and sys.flags.optimize == 0, "Assertion-enabled ownership verification required"
    )


def _stage(directory, inputs, operation, finish):
    """Reuse the observer/retainer; never overlap it with the SIM observer."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=False)
    attempts, values, accounting = [], {}, {}
    calls = stream = None
    started = False

    def take(name, action, **readers):
        if calls is not None:
            calls.stage = name
        return continuity.typed_take(
            directory,
            name,
            action,
            attempts=attempts,
            work="INIT_acquisition_or_transport_work_never_independent_cases",
            readers=readers,
        )

    def start():
        nonlocal calls, stream, started
        stream = (directory / "invocations.jsonl").open("x")
        calls = Calls(stream)
        calls.start()
        started = True

    def failure(error, stage):
        continuity.typed_failure(
            directory,
            stage,
            error,
            readers={
                "inputs": lambda: inputs,
                "available": lambda: values,
                "attempts": lambda: attempts,
                "accounting": lambda: accounting,
            },
        )

    try:
        value = operation(take, values, start)
    except BaseException as error:
        failure(error, "source-failure")
        raise
    finally:
        primary = sys.exception()
        try:
            if started:
                accounting = calls.stop()
            if stream is not None:
                stream.close()
            snapshot.write_json(
                directory / "attempts.json",
                dict(
                    attempts=attempts,
                    invocations=accounting,
                    independent_biological_cases=0,
                    scope=(
                        "All nested setup/verification/RNG/source calls are work; "
                        "acquisition and SIM journals remain separate"
                    ),
                ),
            )
            snapshot.write_json(
                directory / "runtime.json", dict(child=identity(), loaded=inventory())
            )
        except BaseException as secondary:
            if primary is not None:
                primary.add_note("INIT bridge accounting also failed: " + repr(secondary))
            else:
                failure(secondary, "accounting-failure")
                raise
    try:
        require(
            accounting.get("profile_intact") and accounting.get("active_invocations") == 0,
            "Incomplete bridge invocation accounting",
        )
        journal = continuity.reader.bind_calls(directory / "invocations.jsonl", accounting)
        result = finish(value, values, accounting)
        snapshot.write_json(
            directory / "result.json",
            dict(
                result,
                invocation_journal=journal,
                accounting=accounting,
                scientific_acceptance=False,
                independent_biological_cases=0,
            ),
        )
    except BaseException as error:
        failure(error, "publication-failure")
        raise
    return value


def check_acquisition_accounting(accounting, count, *, transport=False):
    counts, phases = accounting["counts"], accounting["phase_counts"]
    require(
        phases.get(phase.__name__ + ".advance:INIT", 0) == (0 if transport else count)
        and phases.get(phase.__name__ + ".advance:SIM", 0) == 0,
        "Original INIT work must be separate from the six SIM branch calls",
    )
    require(
        counts.get(phase.__name__ + ".initialize", 0) == (0 if transport else 1),
        "Count actual setup once; transport may not recreate it",
    )
    require(
        counts.get(run.__name__ + ".verify", 0) > 0, "Actual ownership verification must be counted"
    )
    for name in (
        run.__name__ + ".transition",
        checkpoint.__name__ + ".save_checkpoint",
        checkpoint.__name__ + ".load_checkpoint",
    ):
        require(
            counts.get(name, 0) == 0,
            "SIM/checkpoint work belongs to the existing continuation observer",
        )


def acquire_INIT(directory, *, packet, packet_sha256, declaration=None):
    """Return the actual CompletedInitRun object, using only existing APIs."""
    released()
    inputs = verify_packet(packet, packet_sha256)
    directory = continuity.output_path(
        directory, inputs["repository"], packet, inputs["native_root"]
    )

    def operation(take, values, start):
        supplied = take(
            "closed-INIT-inputs",
            lambda: read_graph(Path(packet) / "INIT-inputs", inputs["INIT_inputs"]),
        )
        actual = supplied["declaration"] if declaration is None else declaration
        values.update(declaration=actual, run_inputs=supplied["run_inputs"])
        take("typed-current-INIT-declaration", lambda: preflight_declaration(actual))
        require(
            checkpoint.codec.fingerprint(actual)
            == checkpoint.codec.fingerprint(supplied["declaration"]),
            "Foreign actual input declaration",
        )
        take("explicit-INIT-run-contract", lambda: run_contract(supplied["run_inputs"]))
        require(
            checkpoint.codec.fingerprint(supplied["run_inputs"]["time_profile"])
            == checkpoint.codec.fingerprint(actual.inputs["time_profile"]),
            "Foreign declared INIT time profile",
        )
        take(
            "explicit-current-input-authority",
            lambda: require(
                type(inputs["provenance"]) is str
                and bool(inputs["provenance"].strip())
                and bool(inputs["input_evidence"])
                and inputs["input_producer"] == inputs["expected_producer"],
                "Missing current input authority/provenance/source-work evidence",
            ),
        )
        take("current-frozen-source", lambda: continuity.running_source(packet, inputs))
        start()
        rng_before = take("process-RNG-before", checkpoint._rng_identity)
        rebound = take("actual-current-declaration-validation", lambda: phase.bind(actual.inputs))
        require(
            checkpoint.codec.fingerprint(rebound) == checkpoint.codec.fingerprint(actual),
            "Supplied typed declaration differs from the current input/owner constructor",
        )
        binding, entry = take(
            "actual-INIT-setup", lambda: phase.initialize(actual), declaration=lambda: actual
        )
        values.update(component_binding=binding, entry=entry)
        contract = take(
            "associate-actual-run-owner", lambda: run_contract(supplied["run_inputs"], binding)
        )
        outer = take("actual-run-binding", lambda: run.bind(contract, binding))
        receipt = take(
            "actual-entry-receipt",
            lambda: run.entry_receipt(outer, entry, provenance=inputs["provenance"]),
        )
        parent = take("actual-run-begin", lambda: run.begin(outer, entry, receipt))
        values.update(binding=outer, initial_parent=parent)
        terminal, _ = take(
            "original-full-INIT-window",
            lambda: run.run_window(outer, parent, stop=binding.calendar.step_count),
            parent=lambda: parent,
        )
        values["terminal"] = terminal
        take(
            "exhausted-original-INIT",
            lambda: continuity.admission.preflight(
                outer,
                terminal,
                expected_binding_identity=outer.identity,
                expected_parent_identity=terminal.identity,
            ),
        )
        completed = take("actual-complete-INIT", lambda: run.complete_INIT(outer, terminal))
        require(
            type(completed) is run.CompletedInitRun
            and completed.binding is outer
            and completed.run is terminal,
            "Only the actual completed INIT return may cross the in-process boundary",
        )
        values["completed"] = completed
        values["retained_graph"] = take(
            "complete-INIT-evidence-graph",
            lambda: write_graph(directory / "retained-completed-INIT", completed),
        )
        require(
            rng_before == take("process-RNG-after", checkpoint._rng_identity),
            "INIT consumed unowned process RNG",
        )
        return completed

    def finish(completed, values, accounting):
        # Binding.calendar performs ownership verification. The actual owners
        # were verified inside the observer; publication reads their raw typed
        # calendar rather than doing uncounted work after the observer stops.
        count = completed.binding.composition.calendar.step_count
        check_acquisition_accounting(accounting, count)
        return dict(
            kind=KIND,
            status="actual_original_INIT_completed",
            packet=continuity.ref(Path(packet) / "acquisition-inputs.json"),
            snapshot=inputs["snapshot"],
            declaration_identity=values["declaration"].identity,
            binding_identity=completed.binding.identity,
            parent_identity=completed.run.identity,
            complete_identity=completed.identity,
            original_INIT_calls=count,
            retained_graph=values["retained_graph"],
            native_derivation_attested=False,
            owners_returned_in_process=True,
            source_input_work_evidence=inputs["input_evidence"],
        )

    return _stage(directory, inputs, operation, finish)


def continue_INIT(
    directory,
    *,
    packet,
    packet_sha256,
    completed,
    acquisition_result,
    acquisition_result_sha256,
    sim_declaration,
):
    """Verify live completed owners, publish once, then call the existing route.

    Root supplies SIM biological inputs after seeing actual INIT owners. No
    callback/template hydrates them, no positive graph is decoded, and no input
    identity/RNG/profile is inferred from software evidence or a receipt.
    """
    released()
    inputs = verify_packet(packet, packet_sha256)
    directory = continuity.output_path(
        directory, inputs["repository"], packet, inputs["native_root"]
    )
    directory.mkdir(parents=True, exist_ok=False)
    acquisition = Path(acquisition_result).resolve()

    def operation(take, values, start):
        values.update(completed=parent_evidence(completed), sim_declaration=sim_declaration)
        require(
            type(completed) is run.CompletedInitRun,
            "Live typed CompletedInitRun required; no archive/receipt parent",
        )
        take(
            "pinned-acquisition-file",
            lambda: continuity.pinned(
                dict(path=str(acquisition), sha256=acquisition_result_sha256)
            ),
        )
        saved = take(
            "actual-acquisition-record",
            lambda: checkpoint.codec.parse_json(
                checkpoint._read(acquisition, checkpoint.codec.DEFAULT_LIMITS.json_bytes),
                checkpoint.codec.DEFAULT_LIMITS,
            ),
        )
        require(
            saved["status"] == "actual_original_INIT_completed"
            and saved["packet"] == continuity.ref(Path(packet) / "acquisition-inputs.json")
            and saved["snapshot"] == inputs["snapshot"]
            and saved["complete_identity"] == completed.identity
            and saved["binding_identity"] == completed.binding.identity
            and saved["parent_identity"] == completed.run.identity,
            "Foreign/incomplete acquisition record; a receipt is not parent admission",
        )
        for name, filename in (("state", "state.json"), ("arrays", "arrays.npz")):
            require(
                continuity.pinned(saved["retained_graph"][name])
                == acquisition.parent / "retained-completed-INIT" / filename,
                "Foreign actual INIT evidence graph",
            )
        check_acquisition_accounting(
            saved["accounting"], completed.binding.composition.calendar.step_count
        )
        continuity.reader.bind_calls(acquisition.parent / "invocations.jsonl", saved["accounting"])
        expected = dict(
            binding_identity=completed.binding.identity, parent_identity=completed.run.identity
        )
        take(
            "exact-INIT-SIM-association",
            lambda: continuity.preflight(
                completed.binding, completed.run, sim_declaration, expected=expected
            ),
        )
        require(
            checkpoint.codec.fingerprint(completed) == saved["retained_graph"]["fingerprint"],
            "Changed actual completed INIT graph",
        )
        take("current-frozen-source", lambda: continuity.running_source(packet, inputs))
        start()
        take("actual-completed-INIT-verification", lambda: run.verify_completed_INIT(completed))
        return completed

    def finish(actual, values, accounting):
        check_acquisition_accounting(
            accounting, actual.binding.composition.calendar.step_count, transport=True
        )
        return dict(
            kind=KIND,
            status="actual_completed_INIT_transport_verified",
            acquisition=continuity.ref(acquisition),
            complete_identity=actual.identity,
            original_INIT_calls=0,
            original_SIM_calls=0,
        )

    try:
        actual = _stage(directory / "transport", inputs, operation, finish)
        # Source was frozen before acquisition. Only append new request files,
        # using actual identities; do not mutate source or an earlier packet.
        require(
            not (Path(packet) / "inputs.json").exists(),
            "Continuation request is exclusive; no retry/overwrite",
        )
        declared = write_graph(Path(packet) / "SIM-declaration", sim_declaration)
        continuation = dict(
            kind=continuity.KIND,
            specification=continuity.SPEC,
            held=True,
            automatic_launch=False,
            release_gates=RELEASES,
            repository=inputs["repository"],
            source_selection=inputs["source_selection"],
            snapshot=inputs["snapshot"],
            expected_producer=inputs["expected_producer"],
            formatter_reference_source_plan=inputs["formatter_reference_source_plan"],
            native_root=inputs["native_root"],
            expected_INIT=dict(
                binding_identity=actual.binding.identity, parent_identity=actual.run.identity
            ),
            positive_INIT_evidence=[
                continuity.ref(acquisition),
                continuity.ref(directory / "transport/result.json"),
            ],
            retained_failed_parent_evidence=inputs["retained_evidence"],
            SIM_declaration=declared,
            actual_entries=0,
            independent_biological_cases=0,
            native_source_numerical_equivalence=False,
            provenance=(
                "Actual in-process completed INIT; "
                "existing continuation independently re-verifies owners"
            ),
        )
        snapshot.write_json(Path(packet) / "inputs.json", continuation)
        result = continuity.actual_continuity(
            directory / "SIM-continuity",
            packet=packet,
            packet_sha256=snapshot.digest(Path(packet) / "inputs.json"),
            init_binding=actual.binding,
            init_parent=actual.run,
        )
        snapshot.write_json(
            directory / "result.json",
            dict(
                status="in_process_INIT_and_continuity_returned",
                acquisition=continuity.ref(acquisition),
                transport=continuity.ref(directory / "transport/result.json"),
                SIM=continuity.ref(directory / "SIM-continuity/result.json"),
                accounting=(
                    "INIT acquisition/transport and SIM3-versus1+2/nested checkpoint journals "
                    "are separate; overlapping work never cases"
                ),
                scientific_acceptance=False,
                independent_biological_cases=0,
            ),
        )
        return result
    except BaseException as error:
        continuity.typed_failure(
            directory,
            "failure",
            error,
            readers={
                "completed": lambda: parent_evidence(completed),
                "sim_inputs": lambda: sim_declaration,
            },
        )
        raise
