"""FR-47's registered tools in the tiers (D323): the references' self-check, the pair rule's and
the judge's synthetic checks, and the parse of the protocol's definitions.

- **The code-blind references' own self-check**
  (validation/assembly_lineages_v2/fr47_references/test_fr47_references.py), unedited, run as a
  script in an interpreter of its own: its last check is that no engine module is loaded, and this
  suite's conftest loads the engine. The child keeps the environment, so the D229 scope map's
  recorder (scripts/gates/scope_inject, on PYTHONPATH) sees what the references read.
- **agreement.py's and fr47_judge.py's checks,** on made-up inputs only.
- **fr47_worlds.check():** every exact definition parses, and with FR-47's build (d) admits W1, W1Δ
  and W2's four rungs. It parses only: nothing runs on the protocol's inputs.

No world is compiled or run; the self-check's tiny master equations take a few seconds.
"""

import subprocess
import sys
from pathlib import Path

from validation import id_table
from validation.assembly_lineages_v2 import agreement, fr47_judge, fr47_worlds

SELF_CHECK = (Path(__file__).resolve().parents[2] / "validation" / "assembly_lineages_v2"
              / "fr47_references" / "test_fr47_references.py")  # fmt: skip


def test_the_references_self_check_passes_in_its_own_interpreter():
    result = subprocess.run([sys.executable, str(SELF_CHECK)], capture_output=True, text=True,
                            timeout=600, cwd=SELF_CHECK.parent)  # fmt: skip
    assert result.returncode == 0, result.stdout[-4000:] + result.stderr[-4000:]
    assert "all passed" in result.stdout


def test_the_pair_rule_and_the_judge_pass_their_synthetic_checks():
    for name, results in (("agreement", agreement.check()), ("fr47_judge", fr47_judge.check())):
        failed = [label for label, r in results.items() if not r["ok"]]
        assert not failed, (name, failed)


def test_every_protocol_definition_parses_and_d_admits_each_world(monkeypatch):
    monkeypatch.setattr(fr47_worlds, "D", id_table.translate(fr47_worlds.D))
    verdicts = fr47_worlds.check()
    assert sorted(verdicts) == ["W1", "W1D", "W2_1024", "W2_256", "W2_4096", "W2_64"]
    for key, verdict in verdicts.items():
        assert verdict == {"exact": "parses", "d": "admitted"}, (key, verdict)
