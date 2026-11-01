"""Held current-source ordinary INIT -> SIM -> checkpoint continuity glue.

The caller must retain a genuinely completed typed INIT run and explicitly
declare SIM inputs. This module never creates an INIT parent or selects a
component fixture. It delegates admission, transition, execution and durable
storage to the existing owners. Formatter correspondence is source-only;
original warm/reference replay and native persistence are separate claims.
"""

import json
import os
import sys
from pathlib import Path

from cells.processes import betse_normal_ecm_molecule_checkpoint as checkpoint
from cells.processes import betse_normal_ecm_molecule_lifecycle as lifecycle
from cells.processes import betse_normal_ecm_molecule_run_lifecycle as run
from validation import source_snapshot as snapshot
from validation.betse import betse_normal_ecm_molecule_checkpoint as preparation
from validation.betse import betse_normal_ecm_molecule_handoff_run as reader
from validation.betse import betse_normal_ecm_molecule_kinetic_reload_checkpoint as admission
from validation.betse import betse_normal_ecm_molecule_kinetic_reload_reference as reference
from validation.betse import betse_normal_ecm_molecule_spatial_event_reference as retention
from validation.betse import betse_normal_ecm_molecule_temporal_continuity as continuity
from validation.betse.betse_normal_channel_join_runtime import inventory
from validation.betse.betse_normal_ecm_init_phase_capture import record_failure
from validation.betse.betse_normal_ecm_molecule_handoff_run_plugin import Calls, identity

FILE = "validation/betse/betse_normal_ecm_molecule_current_continuity.py"
OWNED = (
    FILE,
    "tests/unit/test_betse_normal_ecm_molecule_current_continuity.py",
    "tests/unit/test_betse_normal_ecm_molecule_formatter.py",
)
KIND = "cells.current_source_ordinary_molecule_continuity@1"
RELEASES = reference.RELEASES
SPEC = dict(
    route="ordinary_molecule54_no_intervention_added",
    SIM_source_calls=3,
    checkpoint_after_calls=1,
    branch_calls=dict(uninterrupted=3, prefix=1, continued=2),
    INIT_source="required_retained_exhausted_typed_run_never_created_here",
    SIM_source="explicit_caller_declaration_no_component_fixture_fallback",
    journal_contract="existing_continuous_contract_from_actual_bound_component",
    comparison="complete_closed_checkpoint_graph_including_text_data_aliases_and_journals",
)
require = checkpoint.codec.require


def ref(path):
    path = Path(path).resolve(strict=True)
    require(path.is_file(), "Regular evidence file required")
    return dict(path=str(path), sha256=snapshot.digest(path))


def pinned(row):
    require(type(row) is dict and set(row) == {"path", "sha256"}, "Exact evidence pin required")
    path = Path(row["path"])
    require(path.is_file() and not path.is_symlink(), "Regular pinned evidence required")
    require(ref(path) == row, "Changed pinned evidence: " + str(path))
    return path


def output_path(directory, *sources):
    path = Path(directory).resolve()
    for source in sources:
        source = Path(source).resolve()
        require(
            not path.is_relative_to(source) and not source.is_relative_to(path),
            "Output must be separate from checkout, packet and original source",
        )
    return path


def source_files(repository):
    """Loaded Cells/validation sources only; no historical byte overlays."""
    repository = Path(repository).resolve()
    files = {}
    for name, module in tuple(sys.modules.items()):
        if not name.startswith(("cells.", "validation.")) and name not in {"cells", "validation"}:
            continue
        if getattr(module, "__file__", None) is None:
            continue
        path = Path(module.__file__).resolve()
        require(
            path.is_relative_to(repository) and path.suffix == ".py",
            "Foreign loaded source regime: " + name,
        )
        relative = str(path.relative_to(repository))
        files[relative] = relative
    return files


def preflight(init_binding, init_parent, declaration, *, expected):
    """Structural refusal before any verifier/rebind/setup/RNG/source work."""
    require(
        type(expected) is dict and set(expected) == {"binding_identity", "parent_identity"},
        "Exact externally pinned INIT identities required",
    )
    result = admission.preflight(
        init_binding,
        init_parent,
        expected_binding_identity=expected["binding_identity"],
        expected_parent_identity=expected["parent_identity"],
    )
    require(type(declaration) is dict, "Missing explicit SIM declaration; no fixture fallback")
    require(
        declaration.get("kind") == lifecycle.INPUT_KIND
        and declaration.get("expected_init_binding_identity") == init_binding.composition.identity
        and declaration.get("sim_phase", {}).get("time_profile", {}).get("phase") == "SIM"
        and declaration["sim_phase"].get("flags", {}).get("phase") == "SIM"
        and declaration["sim_phase"].get("flags", {}).get("_run_sim") is True,
        "Foreign explicit SIM/INIT declaration association",
    )
    require(
        "kinetic_reload" not in declaration
        and set(declaration)
        <= {
            "kind",
            "case_id",
            "provenance",
            "expected_init_binding_identity",
            "sim_phase",
            "source_setup",
            "config_equality_receipt",
        },
        "Ordinary route may not select kinetic, supplied event or other owner routes",
    )
    return dict(result, explicit_SIM_inputs=True, fixture_fallback=False)


def prepare(
    repository,
    directory,
    *,
    source_selection,
    source_selection_sha256,
    sim_declaration=None,
    expected_binding_identity=None,
    expected_parent_identity=None,
    positive_INIT_evidence=(),
    failed_parent_evidence=(),
    native_root=reference.native.ROOT,
):
    """Freeze current checkout bytes and a held request, never an actual parent.

    Evidence pins constrain a later run; their existence is not ownership
    admission. Missing positive authority is recorded and remains executable
    refusal. Declaration encoding preserves mapping order, scalar bits/axes and
    aliases with the existing closed graph codec; it executes no setup.
    """
    repository = Path(repository).resolve(strict=True)
    require(Path(__file__).resolve() == repository / FILE, "Prepare from the current checkout")
    selection = Path(source_selection).resolve(strict=True)
    previous = snapshot.verify(selection.parent, manifest_sha256=source_selection_sha256)
    require(selection.name == "SNAPSHOT.json", "Existing snapshot file selection required")
    directory = output_path(directory, repository, selection.parent, native_root)
    directory.mkdir(parents=True, exist_ok=False)
    try:
        files = {name: row["checkout_path"] for name, row in previous["files"].items()}
        require(all(name == path for name, path in files.items()), "No historical source overlay")
        producer = checkpoint.producer_identity()
        files.update(source_files(repository))
        files.update({name: name for name in OWNED})
        files.update(
            {"src/cells/" + name: "src/cells/" + name for name in producer["source_hashes"]}
        )
        plan = json.loads(json.dumps(reference.source_plan(native_root), allow_nan=False))
        expected = dict(
            binding_identity=expected_binding_identity, parent_identity=expected_parent_identity
        )
        for value in expected.values():
            require(value is None or type(value) is str and bool(value), "Explicit INIT identity")
        positive = [ref(path) for path in positive_INIT_evidence]
        failed = [ref(path) for path in failed_parent_evidence]
        declaration = None
        if sim_declaration is not None:
            require(type(sim_declaration) is dict, "Explicit SIM input mapping required")
            encoder = checkpoint.codec.Encoder()
            tree = encoder.capture(sim_declaration)
            declared = directory / "SIM-declaration"
            declared.mkdir()
            encoder.write(declared, tree)
            declaration = dict(
                fingerprint=encoder.seal(tree),
                state=ref(declared / "state.json"),
                arrays=ref(declared / "arrays.npz"),
            )
        manifest = snapshot.freeze(repository, directory / "source", files)
        for name, digest in producer["source_hashes"].items():
            require(
                manifest["files"]["src/cells/" + name]["sha256"] == digest,
                "Producer changed during current-source preparation: " + name,
            )
        # Refuse a concurrent edit to any validator or formatter plan as well.
        snapshot.assert_checkout_unchanged(directory / "source")
        inputs = dict(
            kind=KIND,
            specification=SPEC,
            held=True,
            automatic_launch=False,
            release_gates=RELEASES,
            repository=str(repository),
            source_selection=ref(selection),
            snapshot=ref(directory / "source/SNAPSHOT.json"),
            expected_producer=producer,
            formatter_reference_source_plan=plan,
            native_root=str(Path(native_root).resolve()),
            expected_INIT=expected,
            positive_INIT_evidence=positive,
            retained_failed_parent_evidence=failed,
            SIM_declaration=declaration,
            missing_prerequisites=[
                name
                for name, available in (
                    ("reviewed actual exhausted typed INIT", all(expected.values()) and positive),
                    ("explicit ordinary SIM declaration", declaration is not None),
                    ("Root scientific release/resource selection", False),
                )
                if not available
            ],
            actual_entries=0,
            independent_biological_cases=0,
            native_source_numerical_equivalence=False,
        )
        snapshot.write_json(directory / "inputs.json", inputs)
        return inputs
    except BaseException as error:
        record_failure(
            error,
            stage="prepare-current-ordinary-continuity",
            readers={"source_selection": lambda: str(selection)},
            retain=lambda payload: snapshot.write_json(directory / "failure.json", payload),
        )
        raise


def verify_packet(packet, sha256):
    packet = Path(packet).resolve(strict=True)
    path = pinned(dict(path=str(packet / "inputs.json"), sha256=sha256))
    inputs = checkpoint.codec.parse_json(path.read_bytes(), checkpoint.codec.DEFAULT_LIMITS)
    require(
        inputs["kind"] == KIND
        and inputs["specification"] == SPEC
        and inputs["held"] is True
        and inputs["automatic_launch"] is False
        and inputs["release_gates"] == list(RELEASES),
        "Changed ordinary held route, branch bound or release gates",
    )
    require(pinned(inputs["snapshot"]) == packet / "source/SNAPSHOT.json", "Foreign snapshot")
    manifest = snapshot.verify(packet / "source", manifest_sha256=inputs["snapshot"]["sha256"])
    for name, digest in inputs["expected_producer"]["source_hashes"].items():
        require(
            manifest["files"]["src/cells/" + name]["sha256"] == digest,
            "Incomplete producer/source selection",
        )
    for row in (*inputs["positive_INIT_evidence"], *inputs["retained_failed_parent_evidence"]):
        pinned(row)
    return inputs


def read_declaration(packet, inputs):
    row = inputs["SIM_declaration"]
    require(row is not None, "Missing explicit SIM declaration; no fixture fallback")
    packet = Path(packet).resolve()
    files = {name: pinned(row[name]) for name in ("state", "arrays")}
    require(
        files
        == dict(
            state=packet / "SIM-declaration/state.json",
            arrays=packet / "SIM-declaration/arrays.npz",
        ),
        "Foreign explicit SIM declaration payload",
    )
    limits = checkpoint.codec.DEFAULT_LIMITS
    tree = checkpoint.codec.parse_json(checkpoint._read(files["state"], limits.json_bytes), limits)
    value = checkpoint.codec.decode(tree, checkpoint._read(files["arrays"], limits.archive_bytes))
    require(
        checkpoint.codec.fingerprint(value) == row["fingerprint"] and type(value) is dict,
        "Changed explicit SIM declaration graph",
    )
    return value


def running_source(packet, inputs):
    source = Path(packet).resolve() / "source"
    require(Path(__file__).resolve() == source / FILE, "Run from the prepared source snapshot")
    manifest = snapshot.verify(source, manifest_sha256=inputs["snapshot"]["sha256"])
    require(set(source_files(source)) <= set(manifest["files"]), "Unpinned loaded source")
    require(
        checkpoint.producer_identity() == inputs["expected_producer"],
        "Changed actual source/runtime producer; historical parents are not rebound",
    )
    require(
        json.loads(json.dumps(reference.source_plan(inputs["native_root"]), allow_nan=False))
        == inputs["formatter_reference_source_plan"],
        "Changed current native-formatter reference correspondence",
    )


def same_graph(left_binding, left, right_binding, right):
    """Complete graph comparison; no text, owner, journal or alias projection."""
    fingerprint = checkpoint.codec.fingerprint((left_binding, left))
    require(
        fingerprint == checkpoint.codec.fingerprint((right_binding, right)),
        "Complete ordinary continuity graph differs (data/text/aliases/clocks/owners)",
    )
    return fingerprint


def observe(binding, parent, init_binding, init_parent):
    run.verify(binding, parent)
    require(
        type(binding.composition) is lifecycle.Binding
        and type(parent.active) is lifecycle.SimPhase,
        "Actual ordinary molecule54 SIM owners required",
    )
    previous = parent.entry_receipt["previous_phase"]
    require(
        type(previous) is run.CompletedInitRun
        and previous.binding.identity == init_binding.identity
        and previous.run.identity == init_parent.identity
        and parent.active.source_init.identity == previous.complete_init.identity,
        "Changed actual INIT/SIM/checkpoint phase ancestry",
    )
    require(
        binding.calendar.step_count == SPEC["SIM_source_calls"], "Original three-call SIM bound"
    )
    return dict(
        full_graph=checkpoint.codec.fingerprint((binding, parent)),
        source_INIT_binding=init_binding.identity,
        source_INIT_parent=init_parent.identity,
        source_complete_INIT=previous.complete_init.identity,
        calendar=binding.calendar.identity,
        cursor=parent.cursor,
        status=parent.status,
        accepted_call_journal=run.ions.data(parent.history),
        sampled_call_indices=[sample.call_index for sample in parent.observations],
        scope="complete graph sealed; headless source subset, no native/physical admission",
    )


def check_accounting(accounting):
    """Use actual callable counts, including overlapping validation/load work."""
    require(
        accounting.get("profile_intact") and accounting.get("active_invocations") == 0,
        "Incomplete invocation accounting",
    )
    counts, phases = accounting["counts"], accounting["phase_counts"]
    require(
        phases.get(lifecycle.init.__name__ + ".advance:SIM", 0) == 6
        and phases.get(lifecycle.init.__name__ + ".advance:INIT", 0) == 0
        and counts.get(lifecycle.init.__name__ + ".initialize", 0) == 0,
        "Six real SIM requests required; INIT creation/replay is forbidden in this route",
    )
    for name, expected in (("save_checkpoint", 1), ("load_checkpoint", 1), ("_verify", 2)):
        require(
            counts.get(checkpoint.__name__ + "." + name, 0) == expected,
            "Missing/extra actual nested checkpoint work: " + name,
        )
    require(
        counts.get(run.__name__ + ".transition", 0) == 1
        and counts.get(run.__name__ + ".verify", 0) > 0,
        "Actual transition and ownership verification must be counted",
    )


def actual_continuity(directory, *, packet, packet_sha256, init_binding=None, init_parent=None):
    """Root-only future entry with real in-process typed owners, never a pickle.

    Both existing gates precede output creation. A held packet without genuine
    positive INIT authority is useful source preparation but cannot execute.
    """
    require(
        all(os.environ.get(name) == "1" for name in RELEASES), "Both existing releases required"
    )
    require(
        __debug__ and sys.flags.optimize == 0, "Assertion-enabled ownership verification required"
    )
    inputs = verify_packet(packet, packet_sha256)
    directory = output_path(directory, inputs["repository"], packet, inputs["native_root"])
    directory.mkdir(parents=True, exist_ok=False)
    attempts, accounting, values = [], {}, dict(init_binding=init_binding, init_parent=init_parent)
    calls = stream = None

    def take(name, operation, **readers):
        if calls is not None:
            calls.stage = name
        return retention._take(
            directory,
            name,
            operation,
            attempts=attempts,
            work="actual_or_metadata_work_never_an_independent_biological_case",
            readers={
                key: lambda reader=reader: run.ions.data(reader())
                for key, reader in readers.items()
            },
        )

    def failure(error, stage):
        record_failure(
            error,
            stage=stage,
            readers={
                "inputs": lambda: inputs,
                "available": lambda: run.ions.data(values),
                "attempts": lambda: attempts,
                "invocations": lambda: accounting,
                "exception_chain": lambda: run.ions.data(retention.failures.exception_chain(error)),
            },
            retain=lambda payload: retention.archives.write_archive(directory / stage, payload),
        )

    try:
        # A structural check precedes even configuration decoding or rebind.
        take(
            "required-genuine-INIT",
            lambda: admission.preflight(
                init_binding,
                init_parent,
                expected_binding_identity=inputs["expected_INIT"]["binding_identity"],
                expected_parent_identity=inputs["expected_INIT"]["parent_identity"],
            ),
            **{key: lambda key=key: values[key] for key in values},
        )
        require(
            bool(inputs["positive_INIT_evidence"]), "Missing reviewed positive INIT evidence pins"
        )
        declaration = take("explicit-SIM-declaration", lambda: read_declaration(packet, inputs))
        values["declaration"] = declaration
        take(
            "explicit-INIT-SIM-association",
            lambda: preflight(
                init_binding, init_parent, declaration, expected=inputs["expected_INIT"]
            ),
        )
        take("current-source-runtime-and-formatter", lambda: running_source(packet, inputs))
        stream = (directory / "invocations.jsonl").open("x")
        calls = Calls(stream)
        calls.start()
        take("actual-INIT-verification", lambda: run.verify(init_binding, init_parent))
        initial = checkpoint.codec.fingerprint((init_binding, init_parent))
        binding, parent = preparation.prepare_SIM(
            directory / "SIM",
            init_binding,
            init_parent,
            attempts,
            case="continuous",
            sim_inputs=declaration,
            calls=calls,
        )
        values.update(binding=binding, parent=parent)
        take("actual-SIM-entry", lambda: observe(binding, parent, init_binding, init_parent))
        require(
            parent.cursor == 0 and parent.status == "ready",
            "Actual fresh ordinary SIM entry required",
        )
        untouched = checkpoint.codec.fingerprint((binding, parent))
        rng_before = take("process-RNG-before", checkpoint._rng_identity)
        calls.stage = "uninterrupted-source-calls"
        baseline = preparation.accepted_prefix(
            directory / "uninterrupted", binding, parent, attempts, calls=3
        )
        values["baseline"] = baseline
        calls.stage = "prefix-source-calls"
        prefix = preparation.accepted_prefix(
            directory / "prefix", binding, parent, attempts, calls=1
        )
        values["prefix"] = prefix
        require(
            checkpoint.codec.fingerprint((binding, parent)) == untouched, "Branch mutated SIM entry"
        )
        paused = take("pause", lambda: run.pause(binding, prefix))
        values["paused"] = paused
        require(
            paused.status == "paused" and paused.cursor == 1, "Retain paused prefix disposition"
        )
        saved = continuity._checkpoint_call(
            take,
            "checkpoint-save",
            lambda: checkpoint.save_checkpoint(
                directory / "checkpoint",
                binding,
                paused,
                expected_phase="SIM",
                expected_parent_identity=paused.identity,
            ),
        )
        loaded = continuity._checkpoint_call(
            take,
            "checkpoint-load",
            lambda: checkpoint.load_checkpoint(
                directory / "checkpoint",
                binding=binding,
                expected_phase="SIM",
                expected_parent_identity=paused.identity,
                expected_checkpoint_identity=saved.identity,
                evidence_directory=directory / "load",
            ),
        )
        values.update(loaded_binding=loaded.binding, loaded_parent=loaded.parent)
        require(loaded.failure is None, "Failed checkpoint cannot become a successful continuation")
        take(
            "loaded-complete-graph",
            lambda: same_graph(binding, paused, loaded.binding, loaded.parent),
        )
        take(
            "loaded-phase-ancestry",
            lambda: observe(loaded.binding, loaded.parent, init_binding, init_parent),
        )
        resumed = take("resume", lambda: run.resume(loaded.binding, loaded.parent))
        take("resumed-complete-graph", lambda: same_graph(binding, prefix, loaded.binding, resumed))
        calls.stage = "continued-source-calls"
        continued = preparation.accepted_prefix(
            directory / "continued", loaded.binding, resumed, attempts, calls=2
        )
        values["continued"] = continued
        before = take(
            "uninterrupted-observation",
            lambda: observe(binding, baseline, init_binding, init_parent),
        )
        after = take(
            "continued-observation",
            lambda: observe(loaded.binding, continued, init_binding, init_parent),
        )
        require(
            before == after and baseline.status == continued.status == "exhausted",
            "Complete continuation differs",
        )
        take(
            "final-complete-graph", lambda: same_graph(binding, baseline, loaded.binding, continued)
        )
        require(
            checkpoint.codec.fingerprint((init_binding, init_parent)) == initial,
            "Retained INIT graph mutated",
        )
        require(
            rng_before == take("process-RNG-after", checkpoint._rng_identity),
            "Unowned process RNG consumed",
        )
        result = dict(
            status="ordinary_current_source_conditional_continuity_passed",
            specification=SPEC,
            packet=ref(Path(packet) / "inputs.json"),
            observation=before,
            nested_checkpoint_requests=saved.verification_attempts
            + loaded.receipt.verification_attempts,
            actual_source_timestep_requests=6,
            independent_biological_cases=0,
            native_formatter_correspondence="source-only current reference; no original replay",
            original_source_numerical_equivalence=False,
            native_pickle_or_physical_acceptance=False,
            scientific_acceptance=False,
        )
    except BaseException as error:
        failure(error, "continuity-failure")
        raise
    finally:
        primary = sys.exception()
        try:
            if calls is not None:
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
                        "All setup, repeated verification/rebind, RNG, source calls and "
                        "nested checkpoint work overlap; never cases"
                    ),
                ),
            )
            snapshot.write_json(
                directory / "runtime.json", dict(child=identity(), loaded=inventory())
            )
        except BaseException as secondary:
            if primary is not None:
                primary.add_note("Continuity accounting also failed: " + repr(secondary))
            else:
                failure(secondary, "accounting-failure")
                raise
    try:
        check_accounting(accounting)
        journal = reader.bind_calls(directory / "invocations.jsonl", accounting)
        snapshot.write_json(
            directory / "result.json",
            dict(result, invocation_journal=journal, accounting=accounting),
        )
    except BaseException as error:
        failure(error, "publication-failure")
        raise
    return result
