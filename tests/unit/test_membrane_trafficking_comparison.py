"""FR-2 version 1 against its code-blind references, at operator level (D224: the user's choice
(b), 19 November 2026).

Every row, criterion and plant here is the registered one (validation/membrane_trafficking/
references/interface/comparison_bands.json). Each is evaluated through
validation/tissue/membrane_trafficking_comparison.py, which reads only the interface files and
drives cells.operator.scheduled_membrane_trafficking@1 on the registered drives, in worlds built from the engine's
own fixtures.
- A row passes when |engine - reference| <= its band, the file's own; no tolerance of this lane's
  enters.
- A plant must fail its named row wherever `must_refuse` holds. A zero-power plant row is not
  asserted refused: it carries its kind's reason, which is asserted present.
- T5's criteria are the engine's err(8)/err(16) in (3.5, 4.5), err(16) < 1e-4, and the Lie plant's
  ratio below 2.5, against the exact N at 4 ms.

The compiled rows are evaluated in test_membrane_trafficking_runs.py and
test_membrane_trafficking_batch.py, and T8's rows and plants in test_membrane_trafficking_sheet.py,
on the runs those files already make.
"""

import jax
import pytest

from validation.tissue import membrane_trafficking_comparison as mc

ROWS = [r["id"] for r in mc.rows("operator")]
CRITERIA = [c["id"] for c in mc.interface()[0]["criteria"]]
PLANTS = [(p["plant"], p["row"]) for p in mc.plants("operator")]


@pytest.fixture(scope="module", autouse=True)
def x64():
    jax.config.update("jax_enable_x64", True)


@pytest.fixture(scope="module")
def verdicts():
    return mc.operator_verdicts()


@pytest.fixture(scope="module")
def criteria():
    return mc.criteria()


@pytest.fixture(scope="module")
def planted():
    return mc.plant_verdicts()


@pytest.mark.parametrize("row", ROWS)
def test_row(verdicts, row):
    v = verdicts[row]
    assert v["passed"], (row, v["engine"], v["deviation"], v["band"], v["margin"])


@pytest.mark.parametrize("criterion", CRITERIA)
def test_criterion(criteria, criterion):
    c = criteria[criterion]
    assert c["passed"], (criterion, c["engine"])


@pytest.mark.parametrize(
    "kind, row", PLANTS, ids=[f"plant{i:03d}:{row}" for i, (_, row) in enumerate(PLANTS)]
)
def test_plant(planted, kind, row):
    v = planted[(kind, row)]
    if not v["must_refuse"]:  # Zero power: reported with its reason, never asserted refused.
        assert v["reason"], (kind, row)
        return
    assert v["refused"], (kind, row, v["engine"], v["deviation"], v["band"])
