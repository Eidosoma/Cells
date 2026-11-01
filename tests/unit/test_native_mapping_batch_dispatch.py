"""Metadata-only checks of the real batch dispatcher; no child jobs execute."""

import argparse
import ast
import hashlib
import importlib.abc
import io
import json
import os
import sys
import tempfile
import traceback
import unittest
from contextlib import redirect_stderr
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
RUNNER = "validation/betse/betse_native_multi_cell_tissue_to_grid_software.py"


class DispatchTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.folder = Path(temporary.name)
        self.repo = self.folder / "checkout"
        self.repo.mkdir()
        self.output = self.folder / "output"
        self.cpu = {2}
        self.launched, self.workers, self.freezes = [], [], []
        self.resource_calls = []
        self.drift_after_worker = self.move_cpu_after_worker = False
        self.worker_returncode = 0
        self.snapshot_error = self.policy_error = self.checkout_error = None
        tree = ast.parse((ROOT / RUNNER).read_bytes())
        constants = {}

        def literal(node):
            if isinstance(node, ast.Name):
                return constants[node.id]
            if isinstance(node, ast.Tuple):
                return tuple(literal(item) for item in node.elts)
            return ast.literal_eval(node)

        for node in tree.body:
            if isinstance(node, ast.Assign) and len(node.targets) == 1:
                name = getattr(node.targets[0], "id", None)
                if name in ("OWN", "OWNED", "TEST", "GROUPS", "EXPECTED"):
                    constants[name] = literal(node.value)
        constants["BATCH_GROUPS"] = tuple(constants["GROUPS"])
        self.owned = constants["OWNED"]
        for name in self.owned:
            path = self.repo / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("# synthetic file, never executed\n")
        snapshot = SimpleNamespace(
            freeze=self.freeze,
            digest=self.digest,
            verify=self.verify,
            _selected=self.selected,
            assert_checkout_unchanged=self.checkout,
        )
        resource = SimpleNamespace(
            RLIMIT_AS="address-space",
            setrlimit=lambda *args: self.resource_calls.append(args),
        )
        self.ns = dict(
            constants,
            ROOT=self.repo,
            Path=Path,
            json=json,
            datetime=datetime,
            timezone=timezone,
            traceback=traceback,
            argparse=argparse,
            resource=resource,
            os=SimpleNamespace(sched_getaffinity=lambda pid: set(self.cpu)),
            sys=SimpleNamespace(executable="/synthetic-python"),
            subprocess=SimpleNamespace(Popen=self.popen, run=self.run_worker, DEVNULL=object()),
            runner=SimpleNamespace(BASE=self.folder, source_snapshot=snapshot, write=self.write),
            closure=lambda: {name: self.digest(self.repo / name) for name in self.owned},
            environment=lambda root: {"synthetic_frozen_environment": str(root)},
        )
        names = {"_require_cpu", "launch_batch", "batch_child", "main"}
        nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
        self.assertEqual({n.name for n in nodes}, names)
        exec(compile(ast.Module(body=nodes, type_ignores=[]), str(ROOT / RUNNER), "exec"), self.ns)
        self.proof = {}

    def tearDown(self):
        self.proof.update(
            mocked_controller_commands=self.launched,
            mocked_worker_commands=self.workers,
            metadata_limits=self.resource_calls,
            actual_jobs_executed=0,
        )

    @staticmethod
    def digest(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()

    @staticmethod
    def write(path, value):
        with path.open("x") as stream:
            json.dump(value, stream)

    def freeze(self, repo, destination, files):
        self.freezes.append(str(destination))
        destination.mkdir()
        result = dict(
            git_revision="synthetic-revision",
            files={name: dict(sha256=self.digest(repo / name)) for name in files},
        )
        self.write(destination / "SNAPSHOT.json", result)
        return result

    def verify(self, destination, *, manifest_sha256):
        if self.snapshot_error is not None:
            raise self.snapshot_error
        self.assertEqual(self.digest(destination / "SNAPSHOT.json"), manifest_sha256)

    def selected(self, repo, names):
        if self.policy_error is not None:
            raise self.policy_error
        self.assertEqual(repo, self.repo)
        self.assertEqual(set(names), set(self.owned))

    def checkout(self, frozen):
        if self.checkout_error is not None:
            raise self.checkout_error

    def popen(self, command, **kwargs):
        self.launched.append(
            dict(
                command=command,
                cwd=str(kwargs["cwd"]),
                start_new_session=kwargs["start_new_session"],
            )
        )
        self.assertEqual(kwargs["cwd"], self.output / "controller-source")
        self.assertEqual(kwargs["env"], {"synthetic_frozen_environment": str(kwargs["cwd"])})
        return SimpleNamespace(pid=12345)

    def run_worker(self, command, **kwargs):
        self.workers.append(dict(command=command, cwd=str(kwargs["cwd"])))
        self.assertEqual(kwargs["cwd"], self.repo)
        sealed = json.loads((self.output / "batch-inputs.json").read_text())
        self.assertEqual(
            json.loads(kwargs["env"]["CELLS_MAPPING_EXPECTED_OWNED"]), sealed["owned_source_sha256"]
        )
        folder = Path(command[command.index("--output") + 1])
        folder.mkdir()
        self.write(folder / "result.json", dict(returncode=self.worker_returncode))
        if self.drift_after_worker:
            (self.repo / self.owned[0]).write_text("# changed source\n")
        if self.move_cpu_after_worker:
            self.cpu = {3}
        return SimpleNamespace(returncode=self.worker_returncode)

    def launch(self, *, cpu=2, groups=("lease", "write")):
        self.assertEqual(self.ns["launch_batch"](self.output, groups, cpu=cpu), 0)
        return self.digest(self.output / "batch-inputs.json")

    def finish(self, identity, *, cpu=2):
        code = self.ns["batch_child"](self.output, identity, cpu=cpu)
        path = self.output / ("BATCH-RESULT.json" if code == 0 else "BATCH-FAILURE.json")
        result = json.loads(path.read_text())
        self.proof["terminal"] = result
        return code, result

    def test_declared_cpu_reaches_sealed_input_controller_and_each_worker(self):
        identity = self.launch()
        inputs = json.loads((self.output / "batch-inputs.json").read_text())
        launch = json.loads((self.output / "LAUNCH.json").read_text())
        self.assertEqual((inputs["cpu"], launch["cpu"]), (2, 2))
        self.assertEqual(
            (
                inputs["threads"],
                inputs["memory_bytes"],
                inputs["wall_per_group_seconds"],
                inputs["reserve_bytes"],
            ),
            (1, 2**30, 480, 8 * 2**30),
        )
        self.assertEqual(launch["batch_inputs_sha256"], identity)
        code, result = self.finish(identity)
        self.assertEqual(code, 0)
        self.assertEqual(len(self.workers), 2)
        for call in self.launched + self.workers:
            command = call["command"]
            self.assertEqual(command[command.index("--cpu") + 1], "2")
        self.assertEqual([row["group"] for row in result["outcomes"]], ["lease", "write"])
        self.assertTrue(result["local_saved_result_review_pending"])
        self.assertEqual(result["native_or_scientific_credit"], 0)

    def test_legacy_default_cpu_six_is_preserved(self):
        self.cpu = {6}
        self.assertEqual(self.ns["launch_batch"](self.output, ("write",)), 0)
        identity = self.digest(self.output / "batch-inputs.json")
        self.assertEqual(self.ns["batch_child"](self.output, identity), 0)
        for call in self.launched + self.workers:
            command = call["command"]
            self.assertEqual(command[command.index("--cpu") + 1], "6")

    def test_invalid_cpu_or_affinity_refuses_before_snapshot_or_launch(self):
        for cpu in (True, "2", -1, 6, None):
            with self.assertRaises(ValueError):
                self.launch(cpu=cpu)
        self.cpu = {2, 6}
        with self.assertRaises(ValueError):
            self.launch()
        self.assertEqual(self.freezes, [])
        self.assertEqual(self.launched, [])
        self.assertFalse(self.output.exists())

    def test_duplicate_empty_and_unknown_groups_refuse_without_launch(self):
        for groups in ((), ("write", "write"), ("absent",)):
            with self.assertRaises(ValueError):
                self.launch(groups=groups)
        self.assertFalse(self.output.exists())
        self.assertEqual(self.launched, [])

    def test_prelaunch_checkout_failure_leaves_preparation_without_child(self):
        self.checkout_error = ValueError("changed before detach")
        with self.assertRaises(ValueError) as caught:
            self.launch()
        self.assertIs(caught.exception, self.checkout_error)
        self.assertTrue((self.output / "batch-inputs.json").exists())
        self.assertFalse((self.output / "LAUNCH.json").exists())
        self.assertEqual(self.launched, [])

    def test_input_digest_change_stops_before_any_worker(self):
        self.launch()
        code, result = self.finish("different-digest")
        self.assertEqual(code, 1)
        self.assertIn("preparation changed", result["error"]["message"])
        self.assertEqual(self.workers, [])

    def test_sealed_cpu_mismatch_stops_before_any_worker(self):
        identity = self.launch()
        self.cpu = {6}
        code, result = self.finish(identity, cpu=6)
        self.assertEqual(code, 1)
        self.assertIn("sealed inputs", result["error"]["message"])
        self.assertEqual(self.workers, [])

    def test_boolean_sealed_cpu_cannot_alias_integer_cpu(self):
        self.cpu = {1}
        self.launch(cpu=1)
        path = self.output / "batch-inputs.json"
        data = json.loads(path.read_text())
        data["cpu"] = True
        path.chmod(0o644)
        path.write_text(json.dumps(data))
        code, result = self.finish(self.digest(path), cpu=1)
        self.assertEqual(code, 1)
        self.assertIn("sealed inputs", result["error"]["message"])
        self.assertEqual(self.workers, [])

    def test_controller_affinity_drift_refuses_next_worker_and_retains_first(self):
        identity = self.launch()
        self.move_cpu_after_worker = True
        code, result = self.finish(identity)
        self.assertEqual(code, 1)
        self.assertEqual(len(self.workers), 1)
        self.assertEqual(len(result["outcomes"]), 1)
        self.assertEqual(result["outcomes"][0]["returncode"], 0)
        self.assertIn("declared single", result["error"]["message"])

    def test_source_drift_between_groups_refuses_next_worker(self):
        identity = self.launch()
        self.drift_after_worker = True
        code, result = self.finish(identity)
        self.assertEqual(code, 1)
        self.assertEqual(len(self.workers), 1)
        self.assertEqual(len(result["outcomes"]), 1)
        self.assertIn("Owned source drift", result["error"]["message"])

    def test_failed_worker_is_retained_without_retry_or_next_group(self):
        identity = self.launch()
        self.worker_returncode = 1
        code, result = self.finish(identity)
        self.assertEqual(code, 1)
        self.assertEqual(len(self.workers), 1)
        self.assertEqual(result["outcomes"][0]["returncode"], 1)
        self.assertEqual(
            result["outcomes"][0]["result_sha256"], self.digest(self.output / "lease/result.json")
        )
        self.assertFalse(result["automatic_retry"])
        self.assertEqual(result["native_or_scientific_credit"], 0)

    def test_invalid_frozen_manifest_stops_before_worker(self):
        identity = self.launch()
        self.snapshot_error = ValueError("damaged frozen manifest")
        code, result = self.finish(identity)
        self.assertEqual(code, 1)
        self.assertEqual(result["error"]["message"], str(self.snapshot_error))
        self.assertEqual(self.workers, [])

    def test_source_policy_refusal_stops_before_worker(self):
        identity = self.launch()
        self.policy_error = ValueError("source not selected by Git")
        code, result = self.finish(identity)
        self.assertEqual(code, 1)
        self.assertEqual(result["error"]["message"], str(self.policy_error))
        self.assertEqual(self.workers, [])

    def test_cli_passes_cpu_to_launcher_and_controller(self):
        command = [
            "runner",
            "--output",
            str(self.output),
            "--cpu",
            "2",
            "--batch",
            "--groups",
            "lease",
            "write",
        ]
        with patch.object(sys, "argv", command):
            self.assertEqual(self.ns["main"](), 0)
        identity = self.digest(self.output / "batch-inputs.json")
        command = [
            "runner",
            "--output",
            str(self.output),
            "--cpu",
            "2",
            "--_batch-child",
            "--_batch-inputs-sha256",
            identity,
        ]
        with patch.object(sys, "argv", command):
            self.assertEqual(self.ns["main"](), 0)
        self.assertEqual(len(self.workers), 2)

    def test_cli_preserves_batch_diagnostic_refusal(self):
        command = ["runner", "--output", str(self.output), "--cpu", "2", "--batch", "--diagnostics"]
        with patch.object(sys, "argv", command), redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as caught:
                self.ns["main"]()
        self.assertEqual(caught.exception.code, 2)
        self.assertEqual(self.launched, [])


def main():
    from validation.betse import betse_normal_channel_join_runtime as runtime

    output = Path(os.environ["CELLS_BATCH_DISPATCH_EVIDENCE"])
    attempts, rows = [], []

    class Block(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path=None, target=None):
            if fullname.split(".")[0] in {"cells", "betse", "numpy", "scipy", "PIL", "jax"}:
                attempts.append(fullname)
                raise AssertionError("Scientific imports forbidden")

    class Result(unittest.TextTestResult):
        def record(self, test, outcome, err=None):
            row = dict(id=test.id(), outcome=outcome, proof=getattr(test, "proof", {}))
            if err is not None:
                row["traceback"] = self._exc_info_to_string(err, test)
            rows.append(row)

        def addSuccess(self, test):
            super().addSuccess(test)
            self.record(test, "passed")

        def addFailure(self, test, err):
            super().addFailure(test, err)
            self.record(test, "failed", err)

        def addError(self, test, err):
            super().addError(test, err)
            self.record(test, "error", err)

    blocker = Block()
    sys.meta_path.insert(0, blocker)
    previous, trace = sys.getprofile(), sys.gettrace()

    def guard(frame, event, arg):
        if previous is not None:
            previous(frame, event, arg)
        if event == "call" and "/betse/science/" in frame.f_code.co_filename:
            attempts.append(frame.f_code.co_qualname)
            raise AssertionError("Native source entry forbidden")

    sys.setprofile(guard)
    try:
        result = unittest.TextTestRunner(verbosity=2, resultclass=Result).run(
            unittest.defaultTestLoader.loadTestsFromTestCase(DispatchTests)
        )
    finally:
        sys.setprofile(previous)
        sys.meta_path.remove(blocker)
        (output / "case-results.json").write_text(json.dumps(rows, indent=2) + "\n")
        (output / "native-entry-guard.json").write_text(
            json.dumps(
                dict(
                    attempted=attempts,
                    profile_restored=sys.getprofile() is previous,
                    trace_preserved=sys.gettrace() is trace,
                    real_children_launched=0,
                )
            )
            + "\n"
        )
        (output / "runtime-producers.json").write_text(
            json.dumps(runtime.inventory(), indent=2) + "\n"
        )
    return int(not result.wasSuccessful() or bool(attempts) or sys.gettrace() is not trace)


if __name__ == "__main__":
    raise SystemExit(main())
