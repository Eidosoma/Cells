"""The qualification judges' --backend (an L4 run of a backend variant's judged run C).

The registered W1, W2 and G2-Q1 definitions declare the CPU, and a definition's declared
backend selects its device. With --backend every definition the judges run declares it, on a
copy, and nothing else differs. Without it the definitions are exactly the registered ones.
No engine run.
"""

import copy
import json

import pytest

from validation.tissue import cell_replacement_judge as g2
from validation.tissue import composite_l4_agreement as agreement

PREDICTIONS = {part: agreement.TISSUE / names[0] for part, names in agreement.FILES.items()}


def executions(tree):
    """Every execution block in a definition tree."""
    if isinstance(tree, list):
        return [e for v in tree for e in executions(v)]
    if not isinstance(tree, dict):
        return []
    found = [tree["execution"]] if isinstance(tree.get("execution"), dict) else []
    return found + [e for v in tree.values() for e in executions(v)]


def backends(tree):
    return {e["backend"] for e in executions(tree) if "backend" in e}


@pytest.mark.parametrize("part", ["w1", "w2", "g2"])
def test_without_the_flag_the_definitions_are_the_registered_ones(part):
    text = PREDICTIONS[part].read_text()
    predictions = json.loads(text)
    same, record = agreement.with_backend(predictions, None)
    assert same is predictions and record is None  # The registered path is untouched.
    assert json.dumps(same, sort_keys=True) == json.dumps(json.loads(text), sort_keys=True)
    assert backends(same) == {"cpu"}


@pytest.mark.parametrize("part", ["w1", "w2", "g2"])
def test_with_the_flag_only_the_backend_differs(part):
    predictions = json.loads(PREDICTIONS[part].read_text())
    before = copy.deepcopy(predictions)
    on_gpu, record = agreement.with_backend(predictions, "gpu")
    declared = [e for e in executions(before) if "backend" in e]
    assert record == dict(declared="gpu", definitions_set=len(declared))
    assert backends(on_gpu) == {"gpu"}
    assert predictions == before  # A copy: the loaded predictions are unchanged.
    assert agreement.on_backend(on_gpu, "cpu")[0] == before  # Nothing but the backend moved.


@pytest.mark.parametrize("build", [g2.w37_raw, lambda backend=None: g2.q7_raw(1.0, backend)])
def test_the_g2_judge_sets_the_worlds_it_builds_itself(build):
    """W37 (Q1) and Q7's tissue are built by the judge, not read from its predictions."""
    registered, on_gpu = build(), build(backend="gpu")
    assert backends(registered) == {"cpu"} and backends(on_gpu) == {"gpu"}
    assert agreement.on_backend(on_gpu, "cpu")[0] == registered
    raw = {"execution": {"backend": "cpu"}}
    assert g2.declared(raw, None) is raw
