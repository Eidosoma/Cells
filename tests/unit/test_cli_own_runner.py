"""The command line refuses a model that declares its own runner, before the fixed-step path.

`cells validate` and `cells run` build a fixed-step time grid (core/grid.refinement_times). A model
whose runner is its own declares it as data (RUNNER, the entry's dotted name: the assembly-lineage
family is the first), and both commands refuse it with a ConfigError that names that runner,
never reaching the grid; a fixed-step model validates as before.

Planted error it must catch: without the RUNNER declaration the same definition reaches the
fixed-step grid (shown with a sentinel there), so the refusal is the declaration's doing.
"""

import json
from pathlib import Path

import pytest

import cells.__main__ as cli
from cells.models.assembly_lineages import model as lineages
from tests.assembly_lineage_fixtures import definition, world

ROOT = Path(__file__).resolve().parents[2]


class Reached(Exception):
    """The fixed-step grid was reached."""


@pytest.fixture
def lineage(tmp_path):
    path = tmp_path / "lineage.json"
    path.write_text(json.dumps(definition(world(), fissions=1)))
    return path


@pytest.fixture
def sentinel(monkeypatch):
    def reached(*args, **kwargs):
        raise Reached

    monkeypatch.setattr(cli, "timeline", reached)
    monkeypatch.setattr(cli, "run", reached)


@pytest.mark.parametrize("command", ["validate", "run"])
def test_an_own_runner_model_is_refused_naming_it(command, lineage, sentinel, tmp_path, capsys):
    out = tmp_path / "out"
    args = [command, str(lineage)] + (["--output", str(out)] if command == "run" else [])
    assert cli.main(args) == 2
    error = capsys.readouterr().err
    assert lineages.RUNNER in error and "fixed-step models only" in error
    assert not out.exists()


def test_without_the_declaration_the_fixed_step_path_is_reached(lineage, sentinel, monkeypatch):
    monkeypatch.delattr(lineages, "RUNNER")
    with pytest.raises(Reached):
        cli.main(["validate", str(lineage)])


@pytest.mark.needs_checkout
def test_a_fixed_step_model_still_validates(capsys):
    assert cli.main(["validate", str(ROOT / "configs/reaction_transport_single.json")]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "valid"
