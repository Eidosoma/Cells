"""Synthetic orchestration metadata only; native/model execution is forbidden."""

import copy
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from validation.betse import native_single_cell_prefix_comparison as runner


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def captures(stop="makeECM"):
    stream = {"synthetic_stream": "unchanged"}
    first = {"request": {"identity": "1" * 64}, "native_comparison_inputs": {"synthetic": True}}
    initial = dict(
        identity="2" * 64,
        request_identity=first["request"]["identity"],
        status="source_completed_unqualified",
        constructor_completed=True,
        pre_mesh_completed=True,
        failure_stage=None,
        failure_type=None,
        failure_message=None,
    )
    core = dict(
        identity="3" * 64,
        initial_request=copy.deepcopy(first["request"]),
        initial_state=copy.deepcopy(initial),
    )
    parameter = dict(
        identity="4" * 64,
        core_request=copy.deepcopy(core),
        configuration_json="{}",
        projection="environment_mask"
        if stop in ("make_maskM", "lapENV_P_inv")
        else "initial_geometry",
        grid_descriptor="native_grid_size_yaml_alias@1" if stop != "near_neigh" else None,
    )
    request = dict(
        identity="5" * 64, prefix_request=dict(identity="6" * 64, parameter_request=parameter)
    )
    geometry = dict(
        identity="7" * 64,
        parent_identity="8" * 64,
        request_identity="9" * 64,
        source_completed=True,
        failure_stage=None,
        failure_type=None,
        failure_message=None,
        stream_before=stream,
        stream_after=stream,
        stages=[[name, {"synthetic_cache": name}] for name in runner.METHODS],
    )
    if stop in ("make_maskM", "lapENV_P_inv"):
        geometry.update(
            parameter_projection="environment_mask",
            parameter_store_roster=list(runner.ENVIRONMENT_STORE_ROSTER),
            parameter_store_lines=list(runner.ENVIRONMENT_STORE_LINES),
        )
    continuation = dict(
        law="betse_owned_single_cell_makeECM@1",
        geometry_trial=geometry["identity"],
        parameter_trial="a" * 64,
        selected_descriptor=["synthetic"],
        boundary="ordinary makeECM; stop before environment",
        invalidated_owners=["synthetic"],
        physical_checkpoint_admitted=False,
    )
    ecm = dict(
        identity="b" * 64,
        parent_identity=geometry["identity"],
        request_identity=digest(continuation),
        source_completed=True,
        failure_stage=None,
        failure_type=None,
        failure_message=None,
        stream_before=stream,
        stream_after=stream,
    )
    values = [first, initial, core, request, geometry]
    if stop != "near_neigh":
        values += [continuation, ecm]
    if stop in ("make_maskM", "lapENV_P_inv"):
        environment_request = dict(
            law="betse_owned_single_cell_environment_mask@1",
            parent=ecm["identity"],
            methods=list(runner.native.ENVIRONMENT_STAGES),
            parameter=continuation["parameter_trial"],
            boundary="before first environmental makeLaplacian",
            invalidated_owners=continuation["invalidated_owners"],
            full_make_world_Parameters_YAML_phase_physical_checkpoint=False,
        )
        environment = dict(
            identity="d" * 64,
            parent_identity=ecm["identity"],
            request_identity=digest(environment_request),
            source_completed=True,
            failure_stage=None,
            failure_type=None,
            failure_message=None,
            stream_before=stream,
            stream_after=stream,
            stages=[[name, {"synthetic_cache": name}] for name in runner.native.ENVIRONMENT_STAGES],
        )
        values += [environment_request, environment]
    if stop == "lapENV_P_inv":
        poisson_request = dict(
            law="betse_owned_single_cell_environment_Poisson@1",
            parent=environment["identity"],
            methods=list(runner.native.POISSON_STAGES),
            boundaries=["N,S,E,W=value", "N,S,E,W=flux"],
            boundary="before lapGJ stores after second makeLaplacian",
            invalidated_owners=environment_request["invalidated_owners"],
            full_make_world_phase_physical_checkpoint=False,
        )
        poisson = dict(
            identity="f" * 64,
            parent_identity=environment["identity"],
            request_identity=digest(poisson_request),
            source_completed=True,
            failure_stage=None,
            failure_type=None,
            failure_message=None,
            stream_before=stream,
            stream_after=stream,
            stages=[[name, {"synthetic_cache": name}] for name in runner.native.POISSON_STAGES],
        )
        values += [poisson_request, poisson]
    return values


def source_sites(stop="make_maskM"):
    result = {
        runner.ENVIRONMENT_INLINE_SITE: dict(first_line=494, last_line=494, ast_sha256="e" * 64)
    }
    if stop == "lapENV_P_inv":
        result.update(
            {
                f"betse/science/cells.py:make_world.assignment_{line}": dict(
                    first_line=line, last_line=line, ast_sha256="f" * 64
                )
                for line in (503, 504, 511, 512)
            }
        )
    return result


class ComparisonContracts(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.native_root = self.root / "native"
        self.native_root.mkdir()
        self.native_files = {
            "betse/__init__.py": b"# synthetic package\n",
            "betse/util/__init__.py": b"# synthetic metadata\n",
        }
        for name, raw in self.native_files.items():
            path = self.native_root / name
            path.parent.mkdir(exist_ok=True, parents=True)
            path.write_bytes(raw)
        self.pins = {p: hashlib.sha256(raw).hexdigest() for p, raw in self.native_files.items()}
        self.patch(runner.native, "evaluate", self.forbidden)
        self.patch(
            runner.native,
            "ENVIRONMENT_STAGES",
            ("environment", "assign_grid_len", "make_maskM"),
            create=True,
        )
        self.patch(
            runner.native,
            "POISSON_STAGES",
            ("environment_voltage", "environment_current"),
            create=True,
        )
        self.patch(
            runner.native,
            "methods_for",
            lambda stop: (
                runner.native.METHODS
                + (() if runner.endpoint(stop) == "near_neigh" else ("makeECM",))
                + (("environment", "make_maskM") if stop in ("make_maskM", "lapENV_P_inv") else ())
            ),
            create=True,
        )
        self.patch(
            runner.native,
            "pins_for",
            lambda stop: self.pins if runner.endpoint(stop) != "near_neigh" else {},
            create=True,
        )
        self.patch(
            runner.native,
            "metadata_imports_for",
            lambda stop: ("betse", "betse.util") if runner.endpoint(stop) != "near_neigh" else (),
            create=True,
        )

    @staticmethod
    def forbidden(*args, **kwargs):
        raise AssertionError("No actual native/source evaluation permitted")

    def patch(self, target, name, value, **kwargs):
        item = patch.object(target, name, value, **kwargs)
        self.addCleanup(item.stop)
        return item.start()

    def write(self, path, value):
        path.parent.mkdir(exist_ok=True, parents=True)
        path.write_text(json.dumps(value))
        return path

    def diagnostic(self, stop="makeECM"):
        root = self.root / "diagnostic"
        root.mkdir()
        values = captures(stop)
        rows = []
        for i, (label, value) in enumerate(
            zip(runner.prior.stage_names(stop), values, strict=True)
        ):
            path = self.write(root / f"capture-{i:04d}.json", value)
            rows.append(
                dict(label=label, path=path.name, status="saved", sha256=runner.native.digest(path))
            )
        recorded = dict(
            status="source_completed_unqualified",
            stop_after=stop,
            case=runner.prior.CASES[0],
            plan_sha256="c" * 64,
            completed_stages=list(runner.prior.stage_names(stop)),
            captures=rows,
            observer_error=None,
            source_error=None,
            failed_stage=None,
            interrupted_exception_graph=None,
        )
        self.write(root / "diagnostic.json", recorded)
        result = dict(
            status="completed_unqualified",
            failure=None,
            case=recorded["case"],
            stop_after=stop,
            diagnostic=runner.prior.pin(root / "diagnostic.json"),
        )
        self.write(root / "result.json", result)
        parent = dict(stop_after=stop, configuration={}, runtime_paths=[], external_inputs=[])
        self.patch(runner.prior, "verify_plan", lambda *args: parent)
        return root, recorded, result, parent

    def grant(self, stop="makeECM", *, legacy=False):
        prepared = self.root / "prepared"
        prepared.mkdir()
        values = captures(stop)
        rows = []
        for i, value in enumerate(values):
            path = self.write(self.root / "captures" / str(i), value)
            rows.append(dict(label=runner.prior.stage_names(stop)[i], **runner.prior.pin(path)))
        plan = dict(
            kind=runner.KINDS[0],
            limits=runner.prior.LIMITS,
            stages=["before", *runner.native.methods_for(stop)],
            native_executions=1,
            cells_replays=0,
            cpu=2,
            automatic_retry=False,
            independent_physical_oracle=False,
            physical_geometry_admitted=False,
            full_package_or_phase_admitted=False,
            ordinary_checkpoint_admitted=False,
            case=runner.prior.CASES[0],
            snapshot_sha256="d" * 64,
            external_inputs=[],
            configuration={},
            native_source_root=str(self.native_root),
            runtime_paths=[],
            input_capture={k: rows[0][k] for k in ("path", "sha256")},
        )
        if stop != "near_neigh":
            plan.update(
                owned_geometry={k: rows[4][k] for k in ("path", "sha256")},
                owned_ecm={k: rows[6][k] for k in ("path", "sha256")},
            )
        else:
            plan["owned_trial"] = {k: rows[4][k] for k in ("path", "sha256")}
        if stop in ("make_maskM", "lapENV_P_inv"):
            plan.update(
                owned_environment={k: rows[8][k] for k in ("path", "sha256")},
                environment_stages=list(runner.native.ENVIRONMENT_STAGES),
                original_source_sites=source_sites(stop),
                inline_assignment_sites=source_sites(stop),
            )
        if stop == "lapENV_P_inv":
            plan.update(
                owned_poisson={k: rows[10][k] for k in ("path", "sha256")},
                poisson_stages=list(runner.native.POISSON_STAGES),
                capture_transport=runner.payload.KIND,
            )
        if not legacy:
            plan.update(
                stop_after=stop,
                saved_captures=rows,
                native_metadata_imports=list(runner.native.metadata_imports_for(stop)),
                shared_descriptor_helpers=stop != "near_neigh",
            )
            plan["external_inputs"] = [{k: row[k] for k in ("path", "sha256")} for row in rows]
            plan["external_inputs"] += [
                dict(path=str(self.native_root / p), sha256=h)
                for p, h in runner.native.pins_for(stop).items()
            ]
        review = self.write(self.root / "review.json", {"synthetic_only": True})
        release = dict(
            kind=runner.KINDS[1],
            case=plan["case"],
            snapshot_sha256=plan["snapshot_sha256"],
            allow_one_native_reference=True,
            physical_geometry_admitted=False,
            source_review=runner.prior.pin(review),
        )
        if not legacy:
            release["stop_after"] = stop
        self.patch(runner.prior, "output_path", lambda p: Path(p))
        self.patch(runner.source_snapshot, "verify", lambda *a, **k: None)
        self.patch(runner.os, "sched_getaffinity", lambda pid: {2})

        def save():
            self.write(prepared / "plan.json", plan)
            release["plan_sha256"] = runner.native.digest(prepared / "plan.json")
            return prepared, release["plan_sha256"], self.write(self.root / "release.json", release)

        return plan, release, save

    def test_seven_complete_captures_bind_ecm_and_geometry(self):
        root, _, _, _ = self.diagnostic()
        stop, _, _, rows, declared = runner.saved_prefix(root, self.root / "parent")
        self.assertEqual(stop, "makeECM")
        self.assertEqual(len(rows), 7)
        self.assertEqual(declared, {"synthetic": True})

    def test_legacy_near_endpoint_is_preserved(self):
        root, recorded, result, parent = self.diagnostic("near_neigh")
        for value in (recorded, result, parent):
            del value["stop_after"]
        self.write(root / "diagnostic.json", recorded)
        result["diagnostic"] = runner.prior.pin(root / "diagnostic.json")
        self.write(root / "result.json", result)
        self.assertEqual(runner.saved_prefix(root, self.root / "parent")[0], "near_neigh")

    def test_complete_markers_do_not_hide_missing_errors_or_stage(self):
        root, recorded, result, parent = self.diagnostic()
        for name in (
            "source_error",
            "observer_error",
            "failed_stage",
            "interrupted_exception_graph",
            "stop_after",
            "completed_stages",
        ):
            with self.subTest(name=name):
                changed = copy.deepcopy(recorded)
                changed[name] = (
                    "make_maskM"
                    if name == "stop_after"
                    else []
                    if name == "completed_stages"
                    else {"failed": True}
                )
                self.write(root / "diagnostic.json", changed)
                result["diagnostic"] = runner.prior.pin(root / "diagnostic.json")
                self.write(root / "result.json", result)
                with self.assertRaises(ValueError):
                    runner.saved_prefix(root, self.root / "parent")

    def test_changed_reordered_or_partial_capture_refuses(self):
        root, recorded, result, _ = self.diagnostic()
        for mutation in ("hash", "reorder", "partial", "duplicate"):
            with self.subTest(mutation=mutation):
                changed = copy.deepcopy(recorded)
                if mutation == "hash":
                    changed["captures"][6]["sha256"] = "0" * 64
                elif mutation == "reorder":
                    changed["captures"].reverse()
                elif mutation == "partial":
                    changed["captures"][6]["status"] = "capture_failed"
                else:
                    changed["captures"][6].update(
                        path=changed["captures"][4]["path"], sha256=changed["captures"][4]["sha256"]
                    )
                self.write(root / "diagnostic.json", changed)
                result["diagnostic"] = runner.prior.pin(root / "diagnostic.json")
                self.write(root / "result.json", result)
                with self.assertRaises(ValueError):
                    runner.saved_prefix(root, self.root / "parent")

    def test_lineage_requires_exact_parent_configuration_and_complete_trials(self):
        for mutation in (
            "initial",
            "core",
            "configuration",
            "projection",
            "descriptor",
            "geometry",
            "request",
            "parent",
            "stream",
            "ecm_error",
            "ecm_partial",
            "boolean",
        ):
            with self.subTest(mutation=mutation):
                values = captures()
                if mutation == "initial":
                    values[1]["request_identity"] = "f" * 64
                elif mutation == "core":
                    values[2]["initial_state"]["constructor_completed"] = 1
                elif mutation == "configuration":
                    values[3]["prefix_request"]["parameter_request"]["configuration_json"] = (
                        '{"extra":0}'
                    )
                elif mutation == "projection":
                    values[3]["prefix_request"]["parameter_request"]["projection"] = "height"
                elif mutation == "descriptor":
                    values[3]["prefix_request"]["parameter_request"]["grid_descriptor"] = None
                elif mutation == "geometry":
                    values[5]["geometry_trial"] = "f" * 64
                elif mutation == "request":
                    values[6]["request_identity"] = "f" * 64
                elif mutation == "parent":
                    values[6]["parent_identity"] = "f" * 64
                elif mutation == "stream":
                    values[6]["stream_before"] = {"synthetic_stream": "changed"}
                elif mutation == "ecm_error":
                    values[6]["capture_error"] = {"failed": True}
                elif mutation == "ecm_partial":
                    del values[6]["failure_message"]
                else:
                    values[6]["source_completed"] = 1
                with self.assertRaises(ValueError):
                    runner.capture_lineage(values, {}, "makeECM")

    def test_exact_ecm_release_and_legacy_near_release(self):
        plan, _, save = self.grant()
        self.assertEqual(runner.verify(*save()), plan)

    def test_legacy_release_may_omit_only_near_endpoint(self):
        plan, _, save = self.grant("near_neigh", legacy=True)
        self.assertEqual(runner.verify(*save()), plan)

    def test_ecm_release_requires_endpoint_and_complete_input_pins(self):
        plan, release, save = self.grant()
        original_plan, original_release = copy.deepcopy(plan), copy.deepcopy(release)
        for mutation in (
            "grant_endpoint",
            "plan_endpoint",
            "missing_endpoint",
            "import",
            "native_pin",
            "capture",
            "trial",
            "shared",
        ):
            with self.subTest(mutation=mutation):
                plan.clear()
                plan.update(copy.deepcopy(original_plan))
                release.clear()
                release.update(copy.deepcopy(original_release))
                if mutation == "grant_endpoint":
                    release["stop_after"] = "near_neigh"
                elif mutation == "plan_endpoint":
                    plan["stop_after"] = "make_maskM"
                elif mutation == "missing_endpoint":
                    release.pop("stop_after")
                elif mutation == "import":
                    plan["native_metadata_imports"].append("betse.science.cells")
                elif mutation == "native_pin":
                    plan["external_inputs"].pop()
                elif mutation == "capture":
                    plan["saved_captures"].pop()
                elif mutation == "trial":
                    plan["owned_ecm"] = dict(plan["owned_geometry"])
                else:
                    plan["shared_descriptor_helpers"] = False
                with self.assertRaises(ValueError):
                    runner.verify(*save())

    def test_import_guard_allows_only_exact_metadata_names(self):
        attempts = []
        guard = runner.import_guard(
            {"stop_after": "makeECM", "native_source_root": str(self.native_root)}, attempts
        )
        guard("import", ("betse",))
        guard("import", ("betse.util",))
        for name in (
            "cells",
            "cells.models",
            "jax",
            "jaxlib.x",
            "betse.science",
            "betse.science.cells",
            "betse.util.foreign",
        ):
            with self.subTest(name=name), self.assertRaises(ImportError):
                guard("import", (name,))
        self.assertEqual(len(attempts), 7)
        guard = runner.import_guard({"native_source_root": str(self.native_root)}, [])
        with self.assertRaises(ImportError):
            guard("import", ("betse",))

    def test_each_allowed_module_requires_actual_origin_and_hash(self):
        plan = {"stop_after": "makeECM", "native_source_root": str(self.native_root)}
        modules = {
            name: SimpleNamespace(
                __file__=pin["path"], __spec__=SimpleNamespace(origin=pin["path"])
            )
            for name, pin in runner.metadata_modules(plan).items()
        }
        self.assertEqual(len(runner.verify_metadata_modules(plan, modules)), 2)
        for mutation in ("origin", "file", "foreign", "fileless", "cells", "jax", "bytes"):
            with self.subTest(mutation=mutation):
                current = copy.deepcopy(modules)
                file = self.native_root / "betse/util/__init__.py"
                original = file.read_bytes()
                try:
                    if mutation == "origin":
                        current["betse.util"].__spec__.origin = "foreign"
                    elif mutation == "file":
                        current["betse.util"].__file__ = "foreign"
                    elif mutation == "foreign":
                        current["betse.science.cells"] = SimpleNamespace()
                    elif mutation == "fileless":
                        current["betse.util"].__file__ = None
                    elif mutation == "bytes":
                        file.write_bytes(b"changed")
                    else:
                        current[mutation] = SimpleNamespace()
                    with self.assertRaises(ValueError):
                        runner.verify_metadata_modules(plan, current)
                finally:
                    file.write_bytes(original)

    def test_all_retained_comparison_inputs_are_protected(self):
        plan, _, _ = self.grant()
        self.patch(runner.prior, "execution_output", lambda value, *a: Path(value))
        for row in runner.retained_inputs(plan):
            with self.subTest(path=row["path"]), self.assertRaises(ValueError):
                runner.protected_output(Path(row["path"]).parent, self.root / "prepared", plan)

    def test_conflicting_dependency_pins_are_not_silently_overwritten(self):
        row = dict(path="/synthetic/beartype.py", sha256="a" * 64)
        self.assertEqual(runner.unique_pins([row, row]), [row])
        with self.assertRaises(ValueError):
            runner.unique_pins([row, dict(row, sha256="b" * 64)])

    def prepare_synthetic(self, stop, *, sidecar=False):
        diagnostic, recorded, result, parent_plan = self.diagnostic(stop)
        if sidecar:
            row = recorded["captures"][-1]
            path = diagnostic / row["path"]
            value = runner.prior.read(path)
            value["synthetic_evidence"] = {"raw_bytes_hex": "00" * runner.payload.THRESHOLD}
            path.unlink()
            runner.payload.write(path, value)
            row["sha256"] = runner.prior.pin(path)["sha256"]
            self.write(diagnostic / "diagnostic.json", recorded)
            result["diagnostic"] = runner.prior.pin(diagnostic / "diagnostic.json")
            self.write(diagnostic / "result.json", result)
        parent = self.root / "parent"
        self.write(parent / "plan.json", {"synthetic_parent": True})
        self.write(diagnostic / "root-review.json", {"synthetic_review": True})
        installed = self.root / "installed" / "beartype.py"
        installed.parent.mkdir()
        installed.write_text("# pinned metadata dependency outside overlays\n")
        parent_plan["external_inputs"] = [runner.prior.pin(installed)]
        repository = self.root / "repository"
        image = self.root / "image.pgm"
        image.write_bytes(b"synthetic image metadata; never decoded")
        paths = [
            runner.OWN,
            runner.NATIVE,
            runner.COMPARE,
            runner.TEST,
            runner.ORCHESTRATION_TEST,
            "tests/unit/test_native_single_cell_prefix_compare.py",
            "tests/unit/test_native_single_cell_prefix_payload.py",
            runner.prior.CLOSURE,
        ]
        for name in paths:
            path = repository / name
            path.parent.mkdir(exist_ok=True, parents=True)
            path.write_text("# synthetic closure file\n")
        source_calls = []
        self.patch(runner, "ROOT", repository)
        self.patch(runner.prior, "NATIVE", self.native_root)
        self.patch(runner.prior, "output_path", lambda p: Path(p))
        self.patch(runner.os, "sched_getaffinity", lambda pid: {2})
        self.patch(
            runner.native,
            "inputs",
            lambda raw, conf, **kw: source_calls.append(("inputs", kw)) or (raw, image),
        )
        self.patch(
            runner.native,
            "source_nodes",
            lambda root, **kw: (
                source_calls.append(("source_nodes", kw)) or ([], source_sites(stop))
            ),
        )
        self.patch(
            runner.runpy,
            "run_path",
            lambda *a: {
                "closure": lambda *a: {
                    name: runner.source_snapshot.digest(repository / name) for name in paths
                }
            },
        )

        def freeze(repo, destination, selected):
            destination.mkdir()
            self.write(destination / "SNAPSHOT.json", {"synthetic_selected_files": selected})
            return {"git_revision": "synthetic"}

        self.patch(runner.source_snapshot, "freeze", freeze)
        self.patch(runner.source_snapshot, "assert_checkout_unchanged", lambda *a: None)
        prepared = self.root / "new-prepared"
        plan = runner.prepare(prepared, diagnostic, parent, cpu=2)
        self.assertEqual(plan["stop_after"], stop)
        self.assertEqual(len(plan["saved_captures"]), len(runner.prior.stage_names(stop)))
        self.assertEqual(plan["owned_geometry"], runner.prior.pin(diagnostic / "capture-0004.json"))
        self.assertEqual(plan["owned_ecm"], runner.prior.pin(diagnostic / "capture-0006.json"))
        self.assertNotIn("owned_trial", plan)
        self.assertIn(runner.prior.pin(installed), plan["external_inputs"])
        self.assertEqual(
            source_calls,
            [("inputs", {"stop_after": stop}), ("source_nodes", {"stop_after": stop})],
        )
        self.assertTrue(plan["shared_descriptor_helpers"])
        self.assertFalse(plan["independent_physical_oracle"])
        return plan, diagnostic

    def test_prepare_preserves_installed_descriptor_pins_and_both_trials(self):
        plan, _ = self.prepare_synthetic("makeECM")
        self.assertNotIn("owned_environment", plan)
        self.assertNotIn("environment_stages", plan)
        self.assertNotIn("inline_assignment_sites", plan)

    def test_environment_prepare_binds_three_trials_and_literal_assignment(self):
        plan, diagnostic = self.prepare_synthetic("make_maskM")
        self.assertEqual(
            plan["owned_environment"], runner.prior.pin(diagnostic / "capture-0008.json")
        )
        self.assertEqual(plan["inline_assignment_sites"], source_sites())
        self.assertEqual(plan["environment_stages"], list(runner.native.ENVIRONMENT_STAGES))
        self.assertNotIn("assign_grid_len", plan["stages"])

    def test_nine_complete_captures_bind_environment_endpoint(self):
        root, _, _, _ = self.diagnostic("make_maskM")
        stop, _, _, rows, _ = runner.saved_prefix(root, self.root / "parent")
        self.assertEqual(stop, "make_maskM")
        self.assertEqual(len(rows), 9)
        self.assertEqual([row["label"] for row in rows][-2:], ["environment_request", "make_maskM"])

    def test_environment_lineage_requires_fresh_stores_and_actual_parent(self):
        mutations = (
            "request_projection",
            "trial_projection",
            "missing_plot_store",
            "store_order",
            "store_float",
            "missing_roster",
            "roster_order",
            "request_law",
            "request_parent",
            "parameter",
            "boundary",
            "physical",
            "owners",
            "request_methods",
            "request_extra",
            "trial_parent",
            "request_digest",
            "stream",
            "stage_order",
            "stage_missing",
            "source_failure",
            "capture_failure",
            "missing_failure",
            "true_integer",
        )
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                values = captures("make_maskM")
                geometry, request, environment = values[4], values[7], values[8]
                if mutation == "request_projection":
                    values[3]["prefix_request"]["parameter_request"]["projection"] = (
                        "initial_geometry"
                    )
                elif mutation == "trial_projection":
                    geometry["parameter_projection"] = "initial_geometry"
                elif mutation == "missing_plot_store":
                    geometry["parameter_store_lines"].pop(0)
                elif mutation == "store_order":
                    geometry["parameter_store_lines"].reverse()
                elif mutation == "store_float":
                    geometry["parameter_store_lines"][0] = 521.0
                elif mutation == "missing_roster":
                    geometry["parameter_store_roster"].remove("plot_grid_size")
                elif mutation == "roster_order":
                    geometry["parameter_store_roster"].reverse()
                elif mutation == "request_law":
                    request["law"] = "unregistered"
                elif mutation == "request_parent":
                    request["parent"] = geometry["identity"]
                elif mutation == "parameter":
                    request["parameter"] = "f" * 64
                elif mutation == "boundary":
                    request["boundary"] = "after Poisson"
                elif mutation == "physical":
                    request["full_make_world_Parameters_YAML_phase_physical_checkpoint"] = True
                elif mutation == "owners":
                    request["invalidated_owners"] = []
                elif mutation == "request_methods":
                    request["methods"].reverse()
                elif mutation == "request_extra":
                    request["unbound"] = True
                elif mutation == "trial_parent":
                    environment["parent_identity"] = geometry["identity"]
                elif mutation == "stream":
                    environment["stream_before"] = {"synthetic_stream": "changed"}
                elif mutation == "stage_order":
                    environment["stages"].reverse()
                elif mutation == "stage_missing":
                    environment["stages"].pop(1)
                elif mutation == "source_failure":
                    environment["failure_type"] = "RuntimeError"
                elif mutation == "capture_failure":
                    environment["capture_error"] = {"message": "capture failed"}
                elif mutation == "missing_failure":
                    del environment["failure_message"]
                elif mutation == "true_integer":
                    environment["source_completed"] = 1
                # Reseal mutated declarations: semantic guards must still refuse.
                environment["request_identity"] = (
                    "f" * 64 if mutation == "request_digest" else digest(request)
                )
                with self.assertRaises(ValueError):
                    runner.capture_lineage(values, {}, "make_maskM")

    def test_environment_capture_paths_hashes_and_partial_markers_are_bound(self):
        root, recorded, result, _ = self.diagnostic("make_maskM")
        for index in (7, 8):
            for mutation in ("hash", "status", "duplicate", "label"):
                with self.subTest(index=index, mutation=mutation):
                    changed = copy.deepcopy(recorded)
                    row = changed["captures"][index]
                    if mutation == "hash":
                        row["sha256"] = "0" * 64
                    elif mutation == "status":
                        row["status"] = "capture_failed"
                    elif mutation == "label":
                        row["label"] = "makeECM"
                    else:
                        row.update({k: changed["captures"][6][k] for k in ("path", "sha256")})
                    self.write(root / "diagnostic.json", changed)
                    result["diagnostic"] = runner.prior.pin(root / "diagnostic.json")
                    self.write(root / "result.json", result)
                    with self.assertRaises(ValueError):
                        runner.saved_prefix(root, self.root / "parent")

    def test_environment_release_requires_endpoint_input_and_inline_roster(self):
        plan, release, save = self.grant("make_maskM")
        self.assertEqual(runner.verify(*save()), plan)
        original_plan, original_release = copy.deepcopy(plan), copy.deepcopy(release)
        for mutation in (
            "grant_missing",
            "grant_ecm",
            "environment_input",
            "missing_input_pin",
            "stage_order",
            "inline_missing",
            "inline_digest",
            "inline_line",
            "fake_method",
            "shared_false",
        ):
            with self.subTest(mutation=mutation):
                plan.clear()
                plan.update(copy.deepcopy(original_plan))
                release.clear()
                release.update(copy.deepcopy(original_release))
                if mutation == "grant_missing":
                    release.pop("stop_after")
                elif mutation == "grant_ecm":
                    release["stop_after"] = "makeECM"
                elif mutation == "environment_input":
                    plan["owned_environment"] = dict(plan["owned_ecm"])
                elif mutation == "missing_input_pin":
                    plan["external_inputs"].remove(plan["owned_environment"])
                elif mutation == "stage_order":
                    plan["environment_stages"].reverse()
                elif mutation == "inline_missing":
                    del plan["inline_assignment_sites"]
                elif mutation == "inline_digest":
                    plan["inline_assignment_sites"][runner.ENVIRONMENT_INLINE_SITE][
                        "ast_sha256"
                    ] = "f" * 64
                elif mutation == "inline_line":
                    for key in ("inline_assignment_sites", "original_source_sites"):
                        plan[key][runner.ENVIRONMENT_INLINE_SITE]["first_line"] = 495
                elif mutation == "fake_method":
                    plan["stages"].insert(-1, "assign_grid_len")
                else:
                    plan["shared_descriptor_helpers"] = False
                with self.assertRaises(ValueError):
                    runner.verify(*save())

    def test_environment_keeps_closed_import_permissions_and_input_protection(self):
        plan, _, _ = self.grant("make_maskM")
        for stop in ("environment", "makeLaplacian", "", None, 1):
            with self.subTest(endpoint=stop), self.assertRaises(ValueError):
                runner.endpoint(stop)
        self.assertEqual(set(runner.metadata_modules(plan)), {"betse", "betse.util"})
        attempts = []
        guard = runner.import_guard(plan, attempts)
        guard("import", ("betse.util",))
        with self.assertRaises(ImportError):
            guard("import", ("betse.science.cells",))
        self.patch(runner.prior, "execution_output", lambda value, *a: Path(value))
        self.assertEqual(len(runner.retained_inputs(plan)), 4)
        for row in runner.retained_inputs(plan):
            with self.subTest(path=row["path"]), self.assertRaises(ValueError):
                runner.protected_output(Path(row["path"]), self.root / "prepared", plan)

    def worker_synthetic(self, stop):
        from validation.betse import native_single_cell_prefix_compare as comparator

        plan, _, save = self.grant(stop)
        args = save()
        plan["interpreter"] = str(Path(sys.executable).absolute())
        self.patch(runner, "verify", lambda *a: plan)
        self.patch(runner, "ROOT", args[0] / "source")
        self.patch(runner, "protected_output", lambda value, *a: Path(value))
        self.patch(runner.resource, "setrlimit", lambda *a: None)
        self.patch(runner.sys, "addaudithook", lambda *a: None)
        self.patch(runner.prior, "runtime_inventory", lambda *a: {})
        calls = []
        self.patch(
            runner.native,
            "evaluate",
            lambda *a, **kw: calls.append(kw) or {"stop_after": stop, "synthetic_only": True},
        )
        self.patch(comparator, "compare", self.forbidden)
        if stop == "lapENV_P_inv":
            self.patch(comparator, "compare_ecm", self.forbidden)
            self.patch(comparator, "compare_environment", self.forbidden)
            self.patch(
                comparator,
                "compare_poisson",
                lambda geometry, ecm, environment, poisson, native: dict(
                    exact_match=(
                        geometry["identity"] == "7" * 64
                        and ecm["identity"] == "b" * 64
                        and environment["identity"] == "d" * 64
                        and poisson["identity"] == "f" * 64
                        and native["stop_after"] == "lapENV_P_inv"
                    )
                ),
                create=True,
            )
        elif stop == "make_maskM":
            self.patch(comparator, "compare_ecm", self.forbidden)
            self.patch(
                comparator,
                "compare_environment",
                lambda geometry, ecm, environment, native: dict(
                    exact_match=(
                        geometry["identity"] == "7" * 64
                        and ecm["identity"] == "b" * 64
                        and environment["identity"] == "d" * 64
                        and native["stop_after"] == "make_maskM"
                    )
                ),
                create=True,
            )
        else:
            self.patch(
                comparator,
                "compare_ecm",
                lambda geometry, ecm, native: dict(
                    exact_match=(
                        geometry["identity"] == "7" * 64
                        and ecm["identity"] == "b" * 64
                        and native["stop_after"] == "makeECM"
                    )
                ),
            )
        output = self.root / "output"
        output.mkdir()
        self.assertEqual(runner.worker(*args, output), 0)
        self.assertEqual(calls[0]["stop_after"], stop)
        self.assertTrue((output / "native.json").is_file())
        self.assertTrue((output / "comparison.json").is_file())

    def test_worker_dispatches_two_distinct_saved_inputs_without_science(self):
        self.worker_synthetic("makeECM")

    def test_worker_dispatches_three_distinct_saved_inputs_without_science(self):
        self.worker_synthetic("make_maskM")

    def test_worker_dispatches_four_distinct_saved_inputs_without_science(self):
        self.worker_synthetic("lapENV_P_inv")
        outcome = runner.prior.read(self.root / "output/worker-result.json")
        self.assertEqual(
            outcome["native_files"], runner.payload.files(self.root / "output/native.json")
        )

    def test_poisson_lineage_and_five_inline_assignments_are_required(self):
        values = captures("lapENV_P_inv")
        runner.capture_lineage(values, {}, "lapENV_P_inv")
        sites = source_sites("lapENV_P_inv")
        self.assertEqual(runner.inline_assignment_sites(sites, "lapENV_P_inv"), sites)
        for key in sites:
            with self.subTest(missing=key), self.assertRaises(ValueError):
                runner.inline_assignment_sites(
                    {k: v for k, v in sites.items() if k != key}, "lapENV_P_inv"
                )
        for index, key, value in (
            (9, "parent", "0" * 64),
            (9, "methods", []),
            (9, "boundaries", ["N,S,E,W=flux", "N,S,E,W=value"]),
            (9, "full_make_world_phase_physical_checkpoint", True),
            (10, "stages", []),
            (10, "source_completed", False),
            (10, "parent_identity", "0" * 64),
            (10, "stream_before", {"synthetic_stream": "changed"}),
            (10, "request_identity", "0" * 64),
            (10, "capture_error", {"retained": True}),
        ):
            changed = copy.deepcopy(values)
            changed[index][key] = value
            with self.subTest(index=index, key=key), self.assertRaises(ValueError):
                runner.capture_lineage(changed, {}, "lapENV_P_inv")

    def test_poisson_exact_plan_and_release(self):
        plan, grant, save = self.grant("lapENV_P_inv")
        self.assertEqual(runner.verify(*save()), plan)
        for key in ("capture_transport", "poisson_stages", "owned_poisson"):
            before = plan.pop(key)
            with self.subTest(key=key), self.assertRaises((ValueError, KeyError)):
                runner.verify(*save())
            plan[key] = before
        grant["stop_after"] = "make_maskM"
        with self.assertRaises(ValueError):
            runner.verify(*save())

    def test_poisson_all_sidecar_bytes_require_plan_binding(self):
        plan, _, save = self.grant("lapENV_P_inv")
        row = plan["saved_captures"][-1]
        path = Path(row["path"])
        value = runner.prior.read(path)
        # This is a transport/lineage control, not a fake numerical cache.
        value["synthetic_evidence"] = {"raw_bytes_hex": "00" * runner.payload.THRESHOLD}
        path.unlink()
        all_pins = runner.payload.write(path, value)
        row["sha256"] = all_pins[0]["sha256"]
        plan["owned_poisson"] = all_pins[0]
        plan["external_inputs"] = [
            r for r in plan["external_inputs"] if r["path"] != str(path)
        ] + all_pins[:1]
        with self.assertRaises(ValueError):
            runner.verify(*save())
        plan["external_inputs"] += all_pins[1:]
        self.assertEqual(runner.verify(*save()), plan)
        blob = Path(all_pins[1]["path"])
        blob.write_bytes(b"x" + blob.read_bytes()[1:])
        with self.assertRaises(ValueError):
            runner.verify(*save())

    def test_poisson_preparation_binds_eleven_captures_and_exact_inline_sites(self):
        plan, diagnostic = self.prepare_synthetic("lapENV_P_inv")
        self.assertEqual(plan["owned_poisson"], runner.prior.pin(diagnostic / "capture-0010.json"))
        self.assertEqual(plan["capture_transport"], runner.payload.KIND)
        self.assertEqual(plan["poisson_stages"], list(runner.native.POISSON_STAGES))
        self.assertEqual(plan["inline_assignment_sites"], source_sites("lapENV_P_inv"))
        self.assertNotIn("allow_one_native_reference", plan)

    def test_poisson_preparation_binds_sidecars_without_expanding_numerical_values(self):
        plan, diagnostic = self.prepare_synthetic("lapENV_P_inv", sidecar=True)
        pins = runner.payload.files(diagnostic / "capture-0010.json")
        self.assertEqual(len(pins), 2)
        for pin in pins:
            self.assertIn(pin, plan["external_inputs"])


if __name__ == "__main__":
    unittest.main()
