"""The register owns generated pages and one named block of the Lean README."""

import io
import json
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from tempfile import TemporaryDirectory

from scripts.generate_claims import BEGIN, END, LANE, experiment_text, generate


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
        self.save([self.claim])

    def save(self, claims):
        self.register.write_text(json.dumps({"version": 1, "comparisons": {}, "claims": claims}))

    def test_check_and_regenerate_after_an_edit_and_a_rename(self):
        notes = self.lane / "claims"
        first = notes / "first.md"
        with redirect_stderr(io.StringIO()):
            self.assertFalse(generate(self.lane, check=True))
        self.assertFalse(notes.exists())
        generate(self.lane)
        canonical = first.read_text()
        first.write_text(canonical + "stale\n")
        with redirect_stderr(io.StringIO()):
            self.assertFalse(generate(self.lane, check=True))
        self.assertEqual(first.read_text(), canonical + "stale\n")
        generate(self.lane)
        self.assertEqual(first.read_text(), canonical)
        handwritten = notes / "reading.md"
        handwritten.write_text("A handwritten note.\n")
        self.claim["id"] = "renamed"
        self.save([self.claim])
        generate(self.lane)
        self.assertFalse(first.exists())
        self.assertEqual(handwritten.read_text(), "A handwritten note.\n")
        self.assertTrue(self.readme.read_text().startswith(self.intro))
        self.assertTrue(self.readme.read_text().endswith(self.footer))
        self.assertIn("(claims/renamed.md)", self.readme.read_text())
        renamed = notes / "renamed.md"
        stamp = renamed.stat().st_mtime_ns
        generate(self.lane)
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
        self.assertEqual(candidate.read_text(), "Handwritten\n")
        self.assertEqual(self.readme.read_text(), original)

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
