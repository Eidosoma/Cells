"""D147 enforced on S3's registered cleft egg (D156), apart from the partition worlds.

field_solver_choice.declare(raw) == raw for cleft_egg_engine.definition(), S3's judged world:
the auto choice would change nothing. It is a J1 world, so it lives here rather than in
test_field_solver_enforcement.py, which builds S5's partition worlds: no module may hold a J1
source beside a partition source (the J2 bright line, tests/unit/test_j2_bright_line.py).
"""

from validation.division import cleft_egg_engine
from validation.tissue import field_solver_choice as choice


def test_the_auto_choice_would_change_nothing_on_s3s_cleft_egg():
    raw = cleft_egg_engine.definition()
    assert choice.declare(raw) == raw
