"""FR-43 part 2's code-blind references: their own self-check, run from tests/ (part 3's precedent).

validation/fr43_part2/references/test_fr43p2_reference.py is the references agent's file, and it
stays theirs and in place: this file loads it by path and collects its tests here, so they run on
every gate. It checks the reference model alone (numpy and scipy): the right-hand side's
conservation and books, its free-energy balance, two closed forms and recharging's sign split. It
imports no engine module and compiles no world. Its reason and cost: the references' self-check on
the gate, about 4 s (seconds as the tier tool measures).
"""

import importlib.util
from pathlib import Path

SELF_CHECK = (
    Path(__file__).resolve().parents[2]
    / "validation"
    / "fr43_part2"
    / "references"
    / "test_fr43p2_reference.py"
)

_spec = importlib.util.spec_from_file_location("fr43_part2_references_self_check", SELF_CHECK)
_self_check = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_self_check)

globals().update({k: v for k, v in vars(_self_check).items() if k.startswith("test_")})
