"""Synthetic file/identity/error controls; no numerical or original source calls."""

import ast
import copy
import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from validation.betse import betse_normal_ecm_molecule_material_failure_evidence as evidence


def fingerprint(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def ref(path):
    return dict(path=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest())


def exception_record(error):
    return dict(
        type=type(error).__name__,
        message=str(error),
        cause=None if error.__cause__ is None else exception_record(error.__cause__),
    )


def primitive_record(**updates):
    value = dict.fromkeys(evidence.PRIMITIVE_FIELDS)
    value.update(
        kind="synthetic-primitive",
        journal=[],
        attempts=[],
        work={},
        recovery_errors=[],
        failed=False,
        scientific_acceptance=False,
    )
    value.update(updates)
    return value


class Store:
    """A small injected writer, with a fixed synthetic byte cap and real file pins."""

    def __init__(self, limit=100000):
        self.limit = limit
        self.written = []
        self.fail_roles = set()
        self.after_write = None
        self.before_write = None

    def archive(self, path, payload):
        if self.before_write:
            self.before_write(path, payload)
        path.mkdir(parents=True, exist_ok=False)
        try:
            raw = json.dumps(payload, sort_keys=True, allow_nan=False).encode()
            if len(raw) > self.limit or path.name in self.fail_roles:
                raise ValueError("Synthetic unchanged archive cap/refusal")
        except BaseException:
            (path / "refusal.json").write_text('{"complete_archive":false}')
            raise
        (path / "state.json").write_bytes(raw)
        (path / "arrays.npz").write_bytes(b"synthetic-no-numeric-members")
        manifest = dict(
            kind="cells.material_four_call_evidence@2",
            fingerprint=fingerprint(payload),
            files={name: ref(path / name) for name in ("state.json", "arrays.npz")},
            owner_admission=False,
            live_array_aliases_reconstructed=False,
        )
        (path / "manifest.json").write_text(json.dumps(manifest))
        self.written.append((path, copy.deepcopy(payload)))
        if self.after_write:
            self.after_write(path, payload)
        return path


class FailureEvidenceTests(unittest.TestCase):
    def setUp(self):
        if root := os.environ.get("FAILURE_HELPER_TEST_ARTIFACTS"):
            self.root = Path(root) / self._testMethodName
            self.root.mkdir(parents=True, exist_ok=False)
        else:
            self.temp = tempfile.TemporaryDirectory()
            self.addCleanup(self.temp.cleanup)
            self.root = Path(self.temp.name)
        self.store = Store()

    def journal(self, **updates):
        args = dict(
            archive=self.store.archive,
            ref=ref,
            exception_record=exception_record,
            fingerprint=fingerprint,
        )
        args.update(updates)
        return evidence.Journal(self.root, **args)

    def failure(self):
        cause = TypeError("original cause")
        error = AssertionError("original comparison failed")
        error.__cause__ = cause
        return error

    def saved(self, journal, stage="original-four", value=None):
        value = {"history": [1, 2, 3, 4]} if value is None else value
        journal.save(stage, dict(status="returned", returned=value), selectors={"returned": value})
        return value

    def section(self, result, name):
        return next(row for row in result["sections"] if row["section"] == name)

    def test_module_has_only_stdlib_imports_and_fixed_registries(self):
        tree = ast.parse(Path(evidence.__file__).read_text())
        modules = {n.module.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
        modules.update(
            a.name.split(".")[0]
            for n in ast.walk(tree)
            if isinstance(n, ast.Import)
            for a in n.names
        )
        self.assertLessEqual(modules, {"json", "os", "re", "stat", "pathlib"})
        self.assertEqual(len(evidence.STAGES), 24)
        self.assertEqual(len(set(evidence.STAGES)), 24)
        self.assertEqual(evidence.MAX_PARTIALS, 12)
        self.assertEqual((evidence.JSON_LIMIT, evidence.ARCHIVE_LIMIT), (16 * 2**20, 64 * 2**20))

    def test_successful_stage_registers_exact_roles_only_after_complete_write(self):
        journal = self.journal()
        value = self.saved(journal)
        row = json.loads(journal.journal.read_text())
        self.assertEqual(row["selectors"]["returned"]["path"], ["returned"])
        self.assertEqual(row["selectors"]["returned"]["fingerprint"], fingerprint(value))
        for name, pin in row["archive"]["files"].items():
            self.assertEqual(pin["sha256"], ref(self.root / "original-four" / name)["sha256"])

    def test_missing_or_corrupt_pair_cannot_register(self):
        for fault in ("manifest", "state", "npz", "manifest-digest", "foreign-path"):
            with self.subTest(fault=fault), tempfile.TemporaryDirectory() as tmp:
                self.root = Path(tmp)

                def damage(path, payload, fault=fault):
                    if fault in ("manifest", "state", "npz"):
                        (
                            path
                            / {
                                "manifest": "manifest.json",
                                "state": "state.json",
                                "npz": "arrays.npz",
                            }[fault]
                        ).unlink()
                    else:
                        p = path / "manifest.json"
                        d = json.loads(p.read_text())
                        if fault == "manifest-digest":
                            d["files"]["state.json"]["sha256"] = "0" * 64
                        else:
                            d["files"]["state.json"]["path"] = str(path / "foreign.json")
                        p.write_text(json.dumps(d))

                self.store = Store()
                self.store.after_write = damage
                journal = self.journal()
                with self.assertRaises((ValueError, FileNotFoundError)):
                    self.saved(journal)
                self.assertEqual(journal.completed, {})
                self.assertEqual(journal.journal.read_text(), "")

    def test_unknown_stage_role_and_nonidentical_selector_refuse_before_write(self):
        journal = self.journal()
        original = {"value": 1}
        for stage, selectors in (
            ("foreign", {}),
            ("original-four", {"foreign": original}),
            ("original-four", {"returned": dict(original)}),
        ):
            with self.subTest(stage=stage, selectors=selectors):
                with self.assertRaises(ValueError):
                    journal.save(stage, {"returned": original}, selectors=selectors)
        self.assertEqual(self.store.written, [])

    def test_mutation_during_successful_write_refuses_registration(self):
        journal = self.journal()
        value = [1]
        self.store.after_write = lambda path, payload: value.append(2)
        with self.assertRaisesRegex(ValueError, "changed during archival"):
            self.saved(journal, value=value)
        self.assertEqual(journal.completed, {})
        self.assertTrue((self.root / "original-four/manifest.json").is_file())

    def test_stale_internally_consistent_archive_cannot_register_current_payload(self):
        store_archive = self.store.archive

        def wrong_archive(path, payload):
            return store_archive(path, dict(returned={"foreign": 1}))

        journal = self.journal(archive=wrong_archive)
        with self.assertRaisesRegex(ValueError, "does not match current payload"):
            self.saved(journal)
        self.assertEqual(journal.completed, {})
        self.assertEqual(journal.journal.read_text(), "")
        self.assertTrue((self.root / "original-four/manifest.json").is_file())

    def test_stale_failure_archive_remains_incomplete(self):
        store_archive = self.store.archive

        def wrong_archive(path, payload):
            return store_archive(path, dict(section=path.name, value="wrong"))

        result = self.journal(archive=wrong_archive).retain(
            self.failure(), stage="failure", available={"inputs": [1]}
        )
        self.assertFalse(result["complete"])
        self.assertEqual(self.section(result, "available-inputs")["status"], "incomplete")

    def test_late_failure_uses_verified_refs_without_aggregate_reencoding(self):
        self.store.limit = 1000
        journal = self.journal()
        values = {}
        for stage in evidence.STAGES:
            if stage in ("comparison", "comparison-final"):
                continue
            value = {"numbers": list(range(100)), "stage": stage}
            role = "exact" if stage.startswith("Decimal-raw-") else "returned"
            journal.save(stage, {role: value}, selectors={role: value})
            values[stage] = value
        self.assertGreater(len(json.dumps(values)), self.store.limit)
        count = len(self.store.written)
        error = self.failure()
        result = journal.retain(
            error,
            stage="comparison",
            available=dict(
                native=values["original-four"],
                Decimal100=values["Decimal100"],
                Decimal160=values["Decimal160"],
                last_returned=values["Decimal160"],
                legacy=tuple(values[f"legacy-step-{i}"] for i in range(3)),
            ),
            capture_errors=[],
            evidence_errors=[],
        )
        self.assertTrue(result["complete"])
        self.assertEqual(len(result["completed_stages"]), 22)
        self.assertEqual(len(self.store.written) - count, 2)  # Only the two empty error sections.
        self.assertEqual(self.section(result, "available-native")["status"], "reference")
        self.assertEqual(error.__cause__.args, ("original cause",))

    def test_corrupt_reference_marks_incomplete_but_other_sections_survive(self):
        for member in ("manifest.json", "state.json", "arrays.npz"):
            with self.subTest(member=member), tempfile.TemporaryDirectory() as tmp:
                self.root, self.store = Path(tmp), Store()
                journal = self.journal()
                value = self.saved(journal)
                (self.root / "original-four" / member).write_bytes(b"changed")
                result = journal.retain(
                    self.failure(),
                    stage="comparison",
                    available=dict(native=value, inputs={"fresh": 2}),
                )
                self.assertFalse(result["complete"])
                self.assertEqual(result["completed_stages"][0]["status"], "refused")
                self.assertEqual(self.section(result, "available-inputs")["status"], "saved")

    def test_changed_or_equal_but_distinct_object_is_saved_as_current(self):
        for mutation in (False, True):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as tmp:
                self.root, self.store = Path(tmp), Store()
                journal = self.journal()
                original = self.saved(journal)
                value = original if mutation else copy.deepcopy(original)
                if mutation:
                    value["history"].append(5)
                result = journal.retain(
                    self.failure(), stage="failure", available={"native": value}
                )
                self.assertTrue(result["complete"])
                self.assertEqual(self.section(result, "available-native")["status"], "saved")

    def test_fresh_primitive_fields_override_stale_aggregate_and_keep_journal(self):
        journal = self.journal()
        stale = primitive_record(journal=[{"before": 1}])
        self.saved(journal, "primitive-begin", stale)
        fresh = primitive_record(
            journal=[{"after": 2}],
            attempts=[{"failed": 4}],
            work={"requests": 4},
            recovery_errors=[{"message": "retain"}],
            failed=True,
        )
        result = journal.retain(
            self.failure(), stage="failure", available={"primitive": stale}, current_primitive=fresh
        )
        self.assertTrue(result["complete"])
        for key in evidence.PRIMITIVE_FIELDS:
            self.assertIn(
                self.section(result, "primitive-" + key)["status"], ("saved", "reference")
            )
        payload = json.loads((self.root / "failure/primitive-journal/state.json").read_text())
        self.assertEqual(payload["value"], fresh["journal"])
        self.assertTrue((self.root / "failure/primitive-recovery_errors/manifest.json").exists())

    def test_primitive_without_fresh_explicit_value_is_not_complete(self):
        journal = self.journal()
        result = journal.retain(
            self.failure(), stage="failure", available={"primitive": primitive_record()}
        )
        self.assertFalse(result["complete"])
        self.assertTrue(any(e["where"] == "current-primitive" for e in result["errors"]))

    def test_projection_failure_preserves_raw_return_and_primary_before_capture(self):
        journal = self.journal()
        raw = {"raw": [-0.0, 4]}
        error = self.failure()
        order = []

        def entered(path, payload):
            self.assertTrue((self.root / "failure/primary.json").is_file())
            order.append(path.name)

        self.store.before_write = entered
        result = journal.retain(
            error, stage="primitive-begin", available={"last_returned": "old"}, raw_returned=raw
        )
        self.assertTrue(result["complete"])
        payload = json.loads((self.root / "failure/raw-returned/state.json").read_text())
        self.assertEqual(payload["value"], raw)
        primary = json.loads((self.root / "failure/primary.json").read_text())
        self.assertEqual(primary["primary"]["cause"]["message"], "original cause")
        self.assertIn("raw-returned", order)

    def test_one_section_refusal_does_not_hide_other_partials_or_primary(self):
        journal = self.journal()
        self.store.fail_roles = {"raw-returned", "source-partial-0"}
        error = self.failure()
        result = journal.retain(
            error,
            stage="failure",
            available={"inputs": [1]},
            raw_returned={"raw": 4},
            source_partials=[{"partial": 0}, {"partial": 1}],
            capture_errors=[{"capture": "failed"}],
            evidence_errors=[{"archive": "failed"}],
        )
        self.assertFalse(result["complete"])
        self.assertEqual(self.section(result, "source-partial-1")["status"], "saved")
        self.assertTrue((self.root / "failure/raw-returned/refusal.json").exists())
        self.assertEqual(error.__cause__.args, ("original cause",))
        self.assertTrue(result["upstream_capture_errors"])

    def test_failed_fingerprint_still_attempts_raw_writer_refusal(self):
        journal = self.journal()
        result = journal.retain(
            self.failure(), stage="failure", available={}, raw_returned=object()
        )
        self.assertFalse(result["complete"])
        self.assertTrue((self.root / "failure/raw-returned/refusal.json").exists())

    def test_secondary_handler_reuses_exact_sections_but_mutations_resave(self):
        journal = self.journal()
        value = {"current": [1]}
        error = self.failure()
        first = journal.retain(error, stage="comparison", available={"inputs": value})
        self.assertTrue(first["complete"])
        count = len(self.store.written)
        second = journal.retain(error, stage="failure", available={"inputs": value})
        self.assertTrue(second["complete"])
        self.assertEqual(len(self.store.written), count)
        self.assertEqual(self.section(second, "available-inputs")["status"], "reference")
        third = journal.retain(error, stage="failure", available={})
        self.assertFalse(third["complete"])

    def test_prior_failure_section_corruption_cannot_be_reused_as_complete(self):
        journal = self.journal()
        value = {"current": [1]}
        journal.retain(self.failure(), stage="comparison", available={"inputs": value})
        (self.root / "failure/available-inputs/arrays.npz").unlink()
        result = journal.retain(self.failure(), stage="failure", available={"inputs": value})
        self.assertFalse(result["complete"])
        self.assertEqual(self.section(result, "available-inputs")["status"], "saved")

    def test_closed_available_and_partial_count_refusals_are_truthful(self):
        for fault in ("unknown", "primitive-schema", "partials", "legacy"):
            with self.subTest(fault=fault), tempfile.TemporaryDirectory() as tmp:
                self.root, self.store = Path(tmp), Store()
                journal = self.journal()
                available, partials = {"inputs": [1]}, []
                if fault == "unknown":
                    available["unbounded"] = [1]
                elif fault == "primitive-schema":
                    available["failed_primitive"] = {"journal": []}
                elif fault == "legacy":
                    available["legacy"] = [0] * 4
                else:
                    partials = [0] * 13
                result = journal.retain(
                    self.failure(), stage="failure", available=available, source_partials=partials
                )
                self.assertFalse(result["complete"])
                self.assertTrue((self.root / "failure/primary.json").exists())

    def test_provenance_pin_drift_is_distinct_from_sections(self):
        source = self.root / "packet-inputs.json"
        source.write_text('{"source":"pinned"}')
        journal = self.journal(provenance={"packet": ref(source)})
        source.write_text('{"source":"changed"}')
        result = journal.retain(self.failure(), stage="failure", available={"inputs": [1]})
        self.assertFalse(result["complete"])
        self.assertEqual(self.section(result, "available-inputs")["status"], "saved")
        self.assertTrue(any(e["where"] == "provenance-packet" for e in result["errors"]))

    def test_primary_and_index_IO_failures_never_replace_original(self):
        for target in ("primary.json", "index.json"):
            with self.subTest(target=target), tempfile.TemporaryDirectory() as tmp:
                self.root, self.store = Path(tmp), Store()
                journal, error = self.journal(), self.failure()
                original = evidence._write

                def failing(path, value, target=target, original=original):
                    if path.name == target:
                        raise OSError("synthetic publication failure")
                    return original(path, value)

                with patch.object(evidence, "_write", failing):
                    result = journal.retain(error, stage="failure", available={"inputs": [1]})
                self.assertFalse(result["complete"])
                self.assertEqual(error.__cause__.args, ("original cause",))
                self.assertTrue(error.__notes__)
                if target == "primary.json":
                    self.assertTrue((self.root / "failure/primary-minimal.json").exists())

    def test_upstream_evidence_failure_cannot_report_complete_capture(self):
        result = self.journal().retain(
            self.failure(),
            stage="failure",
            available={},
            evidence_errors=[{"secondary": "prior writer"}],
        )
        self.assertFalse(result["complete"])
        self.assertTrue(result["upstream_evidence_errors"])
        self.assertEqual(self.section(result, "evidence-errors")["status"], "saved")

    def test_projection_gap_keeps_primary_and_attempts_other_available_sections(self):
        journal, error = self.journal(), self.failure()
        cause, args = error.__cause__, error.args
        source_error = {
            "stage": "current-primitive",
            "type": "ValueError",
            "message": "synthetic owned-field projection refusal",
        }
        result = journal.retain(
            error,
            stage="failure",
            available={"inputs": {"current": 4}},
            source_partials=[{"provider": "native", "attempt": 3}],
            evidence_errors=[source_error],
        )
        self.assertFalse(result["complete"])
        self.assertFalse(result["upstream_capture_errors"])
        self.assertTrue(result["upstream_evidence_errors"])
        for role in ("available-inputs", "source-partial-0", "evidence-errors"):
            self.assertEqual(self.section(result, role)["status"], "saved")
        self.assertIs(error.__cause__, cause)
        self.assertEqual(error.args, args)
        primary = json.loads((self.root / "failure/primary.json").read_text())
        self.assertEqual(primary["primary"], exception_record(error))
        errors = json.loads((self.root / "failure/evidence-errors/state.json").read_text())
        self.assertEqual(errors["value"], [source_error])
        published = json.loads((self.root / "failure/index.json").read_text())
        self.assertFalse(published["complete"])
        self.assertTrue(published["upstream_evidence_errors"])

    def test_mutated_failure_section_is_saved_again_without_substitution(self):
        journal = self.journal()
        value = {"current": [1]}
        journal.retain(self.failure(), stage="failure", available={"inputs": value})
        value["current"].append(2)
        result = journal.retain(self.failure(), stage="failure", available={"inputs": value})
        self.assertTrue(result["complete"])
        self.assertEqual(self.section(result, "available-inputs")["status"], "saved")
        payload = json.loads((self.root / "failure-repeat/available-inputs/state.json").read_text())
        self.assertEqual(payload["value"], value)


if __name__ == "__main__":
    unittest.main()
