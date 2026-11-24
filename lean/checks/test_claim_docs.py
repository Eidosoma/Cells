"""The register owns generated pages and one named block of the Lean README."""

import io
import json
import subprocess
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from scripts.generate_claims import (
    BEGIN,
    END,
    LANE,
    check_sources,
    coverage,
    experiment_text,
    generate,
    wet_lab_register,
)


class ClaimDocsTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.lane = Path(temporary.name) / "lean"
        self.lane.mkdir()
        self.readme = self.lane / "README.md"
        self.intro = f"# Proofs\n\n<!-- generated: another-block -->\nKept\n{END}\n\n"
        self.footer = "\n\n## Run instructions\n"
        self.readme.write_text(f"{self.intro}{BEGIN}\n{END}{self.footer}")
        self.claim = {
            "id": "first",
            "title": "First claim",
            "statement": "A proposed relationship.",
            "assumptions": [],
            "formal": {"status": "open", "theorems": {}},
            "numerical": {"status": "open", "comparisons": [], "result": "No comparison yet."},
            "biology": {"status": "open", "observable": "Amount", "unit": "fmol", "evidence": []},
        }
        self.register = self.lane / "claims.json"
        (self.lane / "registry.json").write_text(json.dumps({"law": {}, "operator": {}}))
        self.save([self.claim])

    def save(self, claims, **fields):
        self.register.write_text(
            json.dumps({"version": 1, "comparisons": {}, "claims": claims, **fields})
        )

    def test_check_and_regenerate_after_an_edit_and_a_rename(self):
        notes = self.lane / "claims"
        first = notes / "first.md"
        with redirect_stderr(io.StringIO()):
            self.assertFalse(generate(self.lane, check=True))
        self.assertFalse(notes.exists())
        generate(self.lane)
        canonical = first.read_text()
        catalog = self.lane / "COVERAGE.md"
        self.assertIn("[All claims](COVERAGE.md#category-all)", self.readme.read_text())
        self.assertIn('<a name="category-all"></a>', catalog.read_text())
        self.assertIn("**Measurement sought.** Amount", catalog.read_text())
        first.write_text(canonical + "stale\n")
        with redirect_stderr(io.StringIO()):
            self.assertFalse(generate(self.lane, check=True))
        self.assertEqual(first.read_text(), canonical + "stale\n")
        generate(self.lane)
        self.assertEqual(first.read_text(), canonical)
        handwritten = notes / "reading.md"
        handwritten.write_text("A handwritten note.\n")
        self.claim["id"] = "renamed"
        finding = "Measured |charge| for one cell. [Paper](https://example.org/paper)"
        self.claim["biology"]["finding"] = finding
        self.claim["formal"]["sources"] = {
            "Upstream": "https://github.com/ATOMSLab/LeanDimensionalAnalysis",
            "Local check": "lean/README.md",
        }
        self.claim["category"] = "transport"
        self.save([self.claim], categories={"transport": "Membrane transport"})
        generate(self.lane)
        self.assertFalse(first.exists())
        self.assertEqual(handwritten.read_text(), "A handwritten note.\n")
        self.assertTrue(self.readme.read_text().startswith(self.intro))
        self.assertTrue(self.readme.read_text().endswith(self.footer))
        self.assertIn(
            "[Membrane transport](COVERAGE.md#category-transport) | — | 0 of 1 | 1 open | 1",
            self.readme.read_text(),
        )
        self.assertNotIn("(claims/renamed.md)", self.readme.read_text())
        self.assertIn('<a name="category-transport"></a>', catalog.read_text())
        self.assertEqual(catalog.read_text().count("(claims/renamed.md)"), 1)
        self.assertIn("**Partial evidence.** " + finding.replace("|", r"\|"), catalog.read_text())
        renamed = notes / "renamed.md"
        self.assertIn(finding, renamed.read_text())
        self.assertIn(
            "[Upstream](https://github.com/ATOMSLab/LeanDimensionalAnalysis)", renamed.read_text()
        )
        self.assertIn("[Local check](../README.md)", renamed.read_text())
        stamp = renamed.stat().st_mtime_ns
        self.save([self.claim], categories={"transport": "Transport and osmosis"})
        generate(self.lane)
        self.assertIn(
            "[Transport and osmosis](COVERAGE.md#category-transport)", self.readme.read_text()
        )
        self.assertIn('<a name="category-transport"></a>', catalog.read_text())
        self.assertEqual(renamed.stat().st_mtime_ns, stamp)
        self.assertTrue(generate(self.lane, check=True))

    def test_invalid_register_and_handwritten_collision_preserve_outputs(self):
        notes = self.lane / "claims"
        notes.mkdir()
        original = self.readme.read_text()
        candidate = notes / "first.md"
        candidate.write_text("Handwritten\n")
        with self.assertRaisesRegex(ValueError, "handwritten"):
            generate(self.lane)
        self.save([self.claim, self.claim])
        with self.assertRaisesRegex(ValueError, "duplicate claim"):
            generate(self.lane)
        self.save([self.claim], categories={"transport": "Transport"})
        with self.assertRaisesRegex(ValueError, "needs a category"):
            generate(self.lane)
        self.assertEqual(candidate.read_text(), "Handwritten\n")
        self.assertEqual(self.readme.read_text(), original)
        candidate.unlink()
        self.save([self.claim])
        ledger = self.lane / "WET_LAB_EVIDENCE.md"
        ledger.write_text("Handwritten review\n")
        with self.assertRaisesRegex(ValueError, "handwritten"):
            generate(self.lane)
        self.assertEqual(ledger.read_text(), "Handwritten review\n")

    def test_pairs_require_distinct_records_and_preserve_source_dependence(self):
        biology = self.claim["biology"]
        first = {"dataset_id": "a", "citation": "First group", "doi": "10.1234/same"}
        other = {"dataset_id": "b", "citation": "Second record", "doi": "10.1234/same#fig2"}
        biology["evidence"] = [first, other]
        claims = {"first": self.claim}
        page, _ = wet_lab_register(claims)
        self.assertIn("awaiting their first paired review (1)", page)
        pair = {
            "id": "uptake",
            "assumption": "Uptake increases.",
            "datasets": ["a", "b"],
            "outcome": "both_support",
            "independence": "The two groups collected their own data.",
            "comparison": "The measured rates increased.",
        }
        biology["pairs"] = [pair]
        with self.assertRaisesRegex(ValueError, "publications"):
            wet_lab_register(claims)
        pair["outcome"] = "not_independent"
        page, _ = wet_lab_register(claims)
        self.assertIn("| Independent replication unconfirmed | 1 |", page)
        other["doi"] = "10.1234/different"
        pair["outcome"] = "both_support"
        page, summary = wet_lab_register(claims)
        self.assertIn('<a id="pair-uptake"></a>', page)
        self.assertIn("| Supported by both studies | 1 |", page)
        self.assertIn("two independent studies support", summary)
        for datasets in (["a", "a"], ["a", "unknown"]):
            with (
                self.subTest(datasets=datasets),
                self.assertRaisesRegex(ValueError, "two distinct"),
            ):
                biology["pairs"] = [dict(pair, datasets=datasets)]
                wet_lab_register(claims)
        biology["pairs"] = [pair, dict(pair, id="uptake-again", datasets=["b", "a"])]
        with self.assertRaisesRegex(ValueError, "repeated comparison"):
            wet_lab_register(claims)
        del biology["pairs"]
        biology["evidence"] = [first]
        page, _ = wet_lab_register(claims)
        self.assertIn("Seeking a second dataset", page)

    def test_held_out_conditions_must_be_disjoint_from_calibration(self):
        evidence = {
            "dataset_id": "measured-conditions",
            "url": "https://example.org/observations",
            "role": "held_out_from_fitting",
            "fit": ["C1", "C2"],
            "evaluation": ["C2"],
        }
        with self.assertRaisesRegex(ValueError, "held-out evaluation"):
            experiment_text(evidence, "mV", LANE.parent)

    def test_source_review_compares_disk_to_the_engine_and_driver_pins(self):
        repo = self.lane.parent

        def git(*args):
            return subprocess.run(
                [
                    "git",
                    "-C",
                    str(repo),
                    "-c",
                    "user.name=Fixture",
                    "-c",
                    "user.email=fixture",
                    "-c",
                    "commit.gpgSign=false",
                    *args,
                ],
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()

        git("init", "-q")
        engine, driver = repo / "law.py", self.lane / "run.py"
        engine.write_text("first version")
        git("add", "--", "law.py")
        git("commit", "-qm", "law", "--", "law.py")
        first = git("rev-parse", "HEAD")
        driver.write_text("driver")
        measurement = self.lane / "curve.json"
        measurement.write_text("[0.66]")
        git("add", "--", "lean/run.py", "lean/curve.json")
        git("commit", "-qm", "driver and input", "--", "lean/run.py", "lean/curve.json")
        second = git("rev-parse", "HEAD")
        engine_record = dict(
            kind="engine",
            sources={"law": "law.py#L1"},
            record_inputs={"curve": "lean/curve.json"},
            driver="lean/run.py",
            engine_revision=first,
            record_revision=second,
        )
        reference = dict(
            kind="reference",
            sources={"input": "lean/run.py"},
            driver="lean/run.py",
            record_revision=second,
        )
        comparisons = {"engine": engine_record, "reference": reference}
        self.claim["numerical"]["comparisons"] = list(comparisons)
        self.save([self.claim], comparisons=comparisons)

        self.assertEqual(check_sources(self.lane)["changed_claims"], [])
        self.assertEqual(
            check_sources(self.lane, first)["changed_comparisons"],
            {"engine": ["lean/curve.json", "lean/run.py"], "reference": ["lean/run.py"]},
        )
        measurement.write_text("[0.67]")
        self.assertEqual(
            check_sources(self.lane)["changed_comparisons"], {"engine": ["lean/curve.json"]}
        )
        measurement.write_text("[0.66]")
        engine.write_text("staged")
        git("add", "--", "law.py")
        engine.write_text("first version")
        self.assertEqual(check_sources(self.lane)["changed_claims"], [])
        engine.write_text("edited")
        driver.rename(self.lane / "renamed.py")
        report = check_sources(self.lane)
        self.assertEqual(report["changed_claims"], ["first"])
        self.assertEqual(
            report["changed_comparisons"],
            {"engine": ["law.py", "lean/run.py"], "reference": ["lean/run.py"]},
        )
        engine_record["record_revision"] = first
        self.save([self.claim], comparisons=comparisons)
        with self.assertRaisesRegex(ValueError, "missing cited file lean/run.py"):
            check_sources(self.lane)

    def test_direct_theorems_and_exercised_operators_are_counted_separately(self):
        inventory = {
            "law": {"cells.flux@1": "lean/README.md", "cells.other@1": "lean/README.md"},
            "operator": {"cells.balance@1": "lean/README.md"},
        }
        self.claim["formal"] = {"status": "proved", "about": ["cells.flux@1"]}
        check = {
            "kind": "engine",
            "laws": ["flux@1"],
            "operators": ["balance@1"],
            "record": "lean/README.md",
            "record_revision": "1" * 40,
        }
        page, _ = coverage(inventory, {"first": self.claim}, {"run": check}, self.lane.parent, [])
        rows = [line for line in page.splitlines() if line.startswith("| [")]
        self.assertIn("(claims/first.md) | [run]", rows[0])
        self.assertTrue(rows[1].endswith("| Open | Open |"))
        self.assertIn("| Open | [run]", rows[2])
        self.assertIn("1 of 2 registered laws", page)
        self.assertIn("0 of 1 registered operators", page)
        target = "(claims/first.md#numerical-comparison)"
        for verdict in ("failed", "checked", "open"):
            self.claim["numerical"]["status"] = verdict
            page, _ = coverage(
                inventory, {"first": self.claim}, {"run": check}, self.lane.parent, []
            )
            self.assertEqual(target in page, verdict == "failed")
        check["laws"].append("balance@1")
        with self.assertRaisesRegex(ValueError, "wrong registry type"):
            coverage(inventory, {"first": self.claim}, {"run": check}, self.lane.parent, [])

    def test_live_drift_check_preserves_inventory_until_refresh(self):
        generate(self.lane)
        inventory = {"law": {"cells.new@1": "lean/README.md"}, "operator": {}}
        path = self.lane / "registry.json"
        original = path.read_bytes()
        with patch("scripts.generate_claims.live_inventory", return_value=inventory):
            with redirect_stderr(io.StringIO()):
                self.assertFalse(generate(self.lane, check=True, live_registry=True))
            self.assertEqual(path.read_bytes(), original)
            generate(self.lane, live_registry=True)
        self.assertEqual(json.loads(path.read_text()), inventory)
        self.assertIn(
            "[Laws awaiting a category](COVERAGE.md#uncategorized-laws) | 0 of 1",
            self.readme.read_text(),
        )
        catalog = self.lane / "COVERAGE.md"
        self.assertIn("**Awaiting a direct Lean proof** [`cells.new@1`]", catalog.read_text())
        self.claim["category"] = "transport"
        self.save(
            [self.claim],
            categories={"transport": "Transport"},
            law_categories={"cells.new@1": "transport"},
        )
        generate(self.lane)
        self.assertIn(
            "[Transport](COVERAGE.md#category-transport) | 0 of 1", self.readme.read_text()
        )
        self.assertNotIn("uncategorized-laws", self.readme.read_text())
        self.assertIn("## Transport\n\n**Awaiting a direct Lean proof**", catalog.read_text())
        self.assertTrue(generate(self.lane, check=True))
