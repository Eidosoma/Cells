"""Held real-parent scalar-kinetic reload and checkpoint continuity.

Source AST comparison and structural controls grant no numerical/native credit.
Actual preparation requires an externally retained exhausted INIT, explicit
parent identities, a reviewed current producer and both existing release gates.
No fixture creates an INIT parent; the existing SIM declaration is only a
template with separately declared kinetic edits. All nested work is counted.
"""

import ast
import copy
import inspect
import os
import sys
import textwrap
from pathlib import Path

from cells.processes import betse_normal_ecm_molecule_checkpoint as checkpoint
from cells.processes import betse_normal_ecm_molecule_kinetic_reload as kinetics
from cells.processes import betse_normal_ecm_molecule_lifecycle as lifecycle
from cells.processes import betse_normal_ecm_molecule_run_lifecycle as run
from validation import source_snapshot as snapshot
from validation.betse import betse_normal_ecm_molecule_checkpoint as preparation
from validation.betse.betse_normal_ecm_init_phase_capture import record_failure
from validation.betse.betse_normal_ecm_molecule_handoff_run_plugin import Calls

RELEASES = ("CELLS_ECM_MOLECULE_RUN_LIFECYCLE_RELEASED", "CELLS_ECM_MOLECULE_EVENTS_RELEASED")
NATIVE_ROOT = Path("/mnt/workspaces/Cells/betse-v1.5.0/betse/science/chemistry")
NATIVE_PINS = {
    "molecules.py": "69e50cbca8281d7ececc12d6136846244a0fe273e43b3d1dfaf793ea19cc2926",
    "gene.py": "949657c9282b9109123fabb8380ee9fc05941ecef0d085f196154fa1b6bd87d1",
    "networks.py": "e32741a04c08812342461d18c80676153a6316bbd6bb958861defb23cb321177",
}
OWNED = (
    "src/cells/processes/betse_normal_ecm_molecule_kinetic_reload.py",
    "src/cells/processes/betse_normal_ecm_molecule_lifecycle.py",
    "src/cells/processes/betse_normal_ecm_molecule_lifecycle_setup.py",
    "validation/betse/betse_normal_ecm_molecule_kinetic_reload_checkpoint.py",
    "tests/unit/test_betse_normal_ecm_molecule_kinetic_reload_checkpoint.py",
)
require = kinetics.require


def _body(node):
    statements = copy.deepcopy(node.body)
    if (
        statements
        and isinstance(statements[0], ast.Expr)
        and isinstance(statements[0].value, ast.Constant)
        and type(statements[0].value.value) is str
    ):
        statements.pop(0)
    return ast.dump(ast.Module(body=statements, type_ignores=[]), include_attributes=False)


def source_plan(root=NATIVE_ROOT):
    """Read pinned original bodies, never import or execute native source."""
    root = Path(root).resolve(strict=True)
    methods = (
        ("molecules.py", "MasterOfMolecules", "reinitialize", kinetics.FUNCTIONS[1]),
        ("gene.py", "MasterOfGenes", "reinitialize", kinetics.FUNCTIONS[2]),
        ("networks.py", "MasterOfNetworks", "tissue_init", kinetics.FUNCTIONS[3]),
        ("networks.py", "Molecule", "init_growth", kinetics.FUNCTIONS[4]),
    )
    files, rows = {}, []
    for name, pin in NATIVE_PINS.items():
        path = root / name
        require(
            not path.is_symlink() and snapshot.digest(path) == pin,
            "Changed original kinetic source: " + name,
        )
        files[name] = ast.parse(path.read_text())
    for filename, cls, method, adopted in methods:
        native_cls = next(
            n for n in files[filename].body if isinstance(n, ast.ClassDef) and n.name == cls
        )
        original = next(
            n for n in native_cls.body if isinstance(n, ast.FunctionDef) and n.name == method
        )
        candidate = ast.parse(textwrap.dedent(inspect.getsource(adopted))).body[0]
        require(
            _body(original) == _body(candidate),
            "Kinetic native/adopted method body differs: " + method,
        )
        rows.append(
            dict(
                file=str(root / filename),
                sha256=NATIVE_PINS[filename],
                original_class=cls,
                method=method,
                original_line=original.lineno,
                candidate_module=adopted.__module__,
                complete_body_match=True,
            )
        )
    return dict(
        methods=rows,
        adopted_source=kinetics.source_identity(),
        scope="whole method AST bodies; decorators, annotations and docstrings excluded",
        actual_native_entries=0,
        numerical_parity=False,
    )


def preflight(init_binding, init_parent, *, expected_binding_identity, expected_parent_identity):
    """Pure structural refusal before complete_INIT; no ownership admission."""
    require(
        type(init_binding) is run.Binding
        and type(init_binding.composition) is lifecycle.init.Binding,
        "Missing actual retained INIT binding",
    )
    require(
        type(init_parent) is run.RunState and type(init_parent.active) is lifecycle.init.State,
        "Missing actual retained INIT run parent",
    )
    base, active = init_binding.composition, init_parent.active
    calendar = base.calendar
    require(
        type(calendar) is run.calendars.NativePhaseCalendar
        and calendar.phase == "INIT"
        and type(calendar.step_count) is int
        and 0 <= calendar.step_count <= 3,
        "Foreign INIT phase/calendar",
    )
    require(
        type(expected_binding_identity) is str
        and bool(expected_binding_identity)
        and type(expected_parent_identity) is str
        and bool(expected_parent_identity)
        and init_binding.identity == init_parent.binding_identity == expected_binding_identity
        and init_parent.identity == expected_parent_identity
        and active.binding_identity == base.identity,
        "Foreign exact INIT binding/parent",
    )
    require(
        type(active.clock) is lifecycle.init.Clock
        and type(active.clock.call_index) is int
        and active.clock.call_index == calendar.step_count == base.call_limit
        and active.status == init_parent.status == "exhausted",
        "Failed/paused/capped/incomplete INIT cannot enter kinetic reload",
    )
    return dict(
        cursor=active.clock.call_index,
        numeric_admission=False,
        required_next="actual run.verify and complete_INIT; no fixture parent",
    )


def declaration(completed, changes, *, provenance):
    """Declare edits on the original SIM template after actual INIT admission."""
    require(type(completed) is lifecycle.CompleteInit, "Actual completed INIT record required")
    raw = preparation.fixtures.sim_inputs("zero_INIT_calls", completed)
    selected = dict(
        kind=kinetics.KIND,
        provenance=provenance,
        source_INIT_binding_identity=completed.binding.identity,
        source_INIT_parent_identity=completed.parent.identity,
        source_complete_INIT_identity=completed.identity,
        changes=copy.deepcopy(changes),
    )
    kinetics.selection({kinetics.KEY: selected})
    raw[kinetics.KEY] = selected
    phase = raw["sim_phase"]
    owners = phase["owners"]
    for row in selected["changes"]:
        cfg = owners["handlers"][row["role"]]["network"]["configuration"]
        matches = [m for m in cfg["biomolecules"] if m["name"] == row["species"]]
        require(
            len(matches) == 1 and isinstance(matches[0].get("growth and decay"), dict),
            "Missing existing growth authority in SIM template",
        )
        growth = matches[0]["growth and decay"]
        require(kinetics.same(growth[row["field"]], row["before"]), "Foreign requested before-rate")
        growth[row["field"]] = row["after"]
    general = owners["handlers"]["molecules"]
    owners["configuration"]["general network"] = dict(
        copy.deepcopy(general["network"]["configuration"]),
        channels=copy.deepcopy(general["catalog"]["populations"]),
        **{"implement network": owners["configuration"]["general network"]["implement network"]},
    )
    phase["field"]["network"] = copy.deepcopy(owners["handlers"]["grn"]["network"])
    owners["field"] = copy.deepcopy(phase["field"])
    # No binder/setup executes here. The normal binding/schema/owner guards
    # and full old-to-new kinetic check still run in the actual transition.
    return raw


def prepare(repository, directory, *, source_selection, changes, provenance):
    """Freeze checkout bytes one way; leave missing real parents explicit."""
    selection_path = Path(source_selection).resolve(strict=True)
    previous = snapshot.verify(
        selection_path.parent, manifest_sha256=snapshot.digest(selection_path)
    )
    files = {n: r["checkout_path"] for n, r in previous["files"].items()}
    require(all(n == p for n, p in files.items()), "Historical source overlay refused")
    files.update({n: n for n in OWNED})
    # Validate the scalar request without inventing parent identifiers.
    require(type(provenance) is str and provenance.strip(), "Declared kinetic provenance required")
    kinetics.validate_changes(changes)
    repository, directory = Path(repository).resolve(strict=True), Path(directory).absolute()
    require(
        not directory.resolve().is_relative_to(repository)
        and not directory.resolve().is_relative_to(selection_path.parent),
        "Unsafe output destination",
    )
    directory.mkdir(parents=True, exist_ok=False)
    try:
        manifest = snapshot.freeze(repository, directory / "source", files)
        producer = checkpoint.producer_identity()
        for name, pin in producer["source_hashes"].items():
            require(
                manifest["files"].get("src/cells/" + name, {}).get("sha256") == pin,
                "Omitted or foreign actual kinetic producer: " + name,
            )
        value = dict(
            kind="cells.held_molecule_kinetic_reload_continuity@1",
            changes=changes,
            provenance=provenance,
            source_selection=dict(path=str(selection_path), sha256=snapshot.digest(selection_path)),
            snapshot=dict(
                path=str(directory / "source/SNAPSHOT.json"),
                sha256=snapshot.digest(directory / "source/SNAPSHOT.json"),
            ),
            source_plan=source_plan(),
            expected_producer=producer,
            held=True,
            required_actual_parent=dict(
                INIT_binding=None, INIT_parent=None, exact_expected_identities=None
            ),
            release_gates=RELEASES,
            cuts=(1, 2),
            independent_biological_cases=0,
            actual_entries=0,
            automatic_launch=False,
        )
        snapshot.write_json(directory / "inputs.json", value)
        return value
    except BaseException as error:
        record_failure(
            error,
            stage="prepare-kinetic-reload",
            readers={"changes": lambda: changes},
            retain=lambda v: snapshot.write_json(directory / "failure.json", v),
        )
        raise


def prepare_sim(directory, init_binding, init_parent, attempts, *, changes, provenance, calls=None):
    directory = Path(directory)
    directory.mkdir(exist_ok=False)
    retain = preparation._retainer(directory, attempts)

    def take(name, operation, **readers):
        if calls is not None:
            calls.stage = name
        return retain(name, operation, **readers)

    complete = take(
        "actual-complete-INIT",
        lambda: run.complete_INIT(init_binding, init_parent),
        init_binding=init_binding,
        init_parent=init_parent,
    )
    raw = take(
        "declared-kinetic-SIM",
        lambda: declaration(complete.complete_init, changes, provenance=provenance),
        complete=complete,
        changes=changes,
    )
    component = take("SIM-component-binding", lambda: lifecycle.bind(raw), raw=raw)
    contract = take(
        "SIM-run-contract", lambda: preparation.fixtures.declaration("zero_INIT_calls", component)
    )
    return take(
        "actual-INIT-to-SIM",
        lambda: run.transition(
            init_binding, init_parent, component, contract, provenance=provenance
        ),
        init_binding=init_binding,
        init_parent=init_parent,
        component=component,
        contract=contract,
    )


def actual_continuity(
    directory,
    *,
    changes,
    provenance,
    cut,
    init_binding=None,
    init_parent=None,
    expected_binding_identity=None,
    expected_parent_identity=None,
    expected_producer=None,
):
    """Held actual route. Existing producers own all setup, checks and load."""
    require(
        all(os.environ.get(name) == "1" for name in RELEASES), "Both existing releases required"
    )
    require(type(cut) is int and cut in (1, 2), "Original three-call cut required")
    kinetics.validate_changes(changes)
    require(
        type(provenance) is str and bool(provenance.strip()), "Declared kinetic provenance required"
    )
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=False)
    (directory / "operations").mkdir()
    attempts, values, accounting = [], {}, {}
    retain = preparation._retainer(directory / "operations", attempts)
    calls = stream = None

    def take(name, operation, **readers):
        if calls is not None:
            calls.stage = name
        return retain(name, operation, **readers)

    try:
        take(
            "required-actual-INIT",
            lambda: preflight(
                init_binding,
                init_parent,
                expected_binding_identity=expected_binding_identity,
                expected_parent_identity=expected_parent_identity,
            ),
            init_binding=init_binding,
            init_parent=init_parent,
            changes=changes,
            provenance=provenance,
            calls=calls,
        )
        require(
            type(expected_producer) is dict and checkpoint.producer_identity() == expected_producer,
            "Missing or foreign reviewed kinetic source/runtime producer",
        )
        take("original-source-plan", source_plan)
        stream = (directory / "invocations.jsonl").open("x")
        calls = Calls(stream)
        calls.start()
        take("actual-INIT-verification", lambda: run.verify(init_binding, init_parent))
        binding, parent = prepare_sim(
            directory / "SIM",
            init_binding,
            init_parent,
            attempts,
            changes=changes,
            provenance=provenance,
        )
        values.update(binding=binding, parent=parent)
        fp = checkpoint.codec.fingerprint
        untouched = fp((binding, parent))
        rng_before = take("global-RNG-before", checkpoint._rng_identity)
        calls.stage = "uninterrupted-source-calls"
        baseline = preparation.accepted_prefix(
            directory / "uninterrupted", binding, parent, attempts, calls=3
        )
        calls.stage = "prefix-source-calls"
        prefix = preparation.accepted_prefix(
            directory / "prefix", binding, parent, attempts, calls=cut
        )
        require(fp((binding, parent)) == untouched, "Continuation mutated retained entry graph")
        paused = take("pause", lambda: run.pause(binding, prefix))
        values.update(baseline=baseline, prefix=prefix, paused=paused)
        saved = None

        def save():
            nonlocal saved
            saved = checkpoint.save_checkpoint(
                directory / "checkpoint",
                binding,
                paused,
                expected_phase="SIM",
                expected_parent_identity=paused.identity,
            )
            require(
                type(saved) is checkpoint.Receipt
                and type(saved.verification_attempts) is int
                and saved.verification_attempts > 0,
                "Missing actual checkpoint verification work",
            )
            return dict(vars(saved), directory=str(saved.directory))

        take("checkpoint-save", save)
        loaded = None

        def load():
            nonlocal loaded
            loaded = checkpoint.load_checkpoint(
                directory / "checkpoint",
                binding=binding,
                expected_phase="SIM",
                expected_parent_identity=paused.identity,
                expected_checkpoint_identity=saved.identity,
                evidence_directory=directory / "load",
            )
            require(
                type(loaded) is checkpoint.Loaded
                and type(loaded.receipt) is checkpoint.Receipt
                and type(loaded.receipt.verification_attempts) is int
                and loaded.receipt.verification_attempts > 0,
                "Missing actual nested checkpoint load verification work",
            )
            return dict(vars(loaded.receipt), directory=str(loaded.receipt.directory))

        take("checkpoint-load", load)
        values["loaded_parent"] = loaded.parent
        require(
            fp((binding, paused)) == fp((loaded.binding, loaded.parent)),
            "Loaded complete graph differs",
        )
        resumed = take("resume", lambda: run.resume(loaded.binding, loaded.parent))
        require(
            fp((binding, prefix)) == fp((loaded.binding, resumed)), "Resume changed retained graph"
        )
        calls.stage = "restored-source-calls"
        continued = preparation.accepted_prefix(
            directory / "continued", loaded.binding, resumed, attempts, calls=3 - cut
        )
        values["continued"] = continued
        require(
            baseline.status == continued.status == "exhausted"
            and fp((binding, baseline)) == fp((loaded.binding, continued)),
            "Full uninterrupted/restored state, journal or sampling differs",
        )
        require(
            rng_before == take("global-RNG-after", checkpoint._rng_identity), "Unowned RNG consumed"
        )
        result = dict(
            status="conditional_kinetic_reload_continuity_passed",
            cut=cut,
            parent=init_parent.identity,
            binding=binding.identity,
            full_graph=fp((binding, baseline)),
            source_receipt=lifecycle.ions.data(
                kinetics.resolve(binding.composition, baseline.active)
            ),
            nested_checkpoint_requests=saved.verification_attempts
            + loaded.receipt.verification_attempts,
            independent_biological_cases=0,
            native_or_physical_acceptance=False,
        )
    except BaseException as error:
        record_failure(
            error,
            stage="kinetic-reload-continuity",
            readers={
                "init_binding": lambda: init_binding,
                "init_parent": lambda: init_parent,
                "changes": lambda: changes,
                "available": lambda: values,
                "attempts": lambda: attempts,
                "partial": lambda error=error: getattr(error, "partial", None),
            },
            retain=lambda v: preparation.archives.write_archive(
                directory / "failure", lifecycle.ions.data(v)
            ),
        )
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
                    scope=(
                        "All overlapping setup/verification/RNG/timestep/nested checkpoint "
                        "calls are work, not cases"
                    ),
                ),
            )
        except BaseException as secondary:
            if primary is not None:
                primary.add_note("Kinetic accounting retention also failed: " + repr(secondary))
            else:
                raise
    try:
        require(
            accounting.get("profile_intact") and accounting.get("active_invocations") == 0,
            "Incomplete kinetic invocation accounting",
        )
        snapshot.write_json(directory / "result.json", result)
    except BaseException as error:
        record_failure(
            error,
            stage="kinetic-result-publication",
            readers={
                "result": lambda: result,
                "accounting": lambda: accounting,
                "available": lambda: values,
                "attempts": lambda: attempts,
            },
            retain=lambda v: preparation.archives.write_archive(
                directory / "publication-failure", lifecycle.ions.data(v)
            ),
        )
        raise
    return result
