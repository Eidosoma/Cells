"""D147 for composite definitions (D156): the field solver a cells.model.resolved_pump_composite@1 declares.

validation/tissue/field_solver_choice.py decides a composite by its inner model
(cells.model.resolved_pump_composite@1 admits cells.model.resolved_pump_tissue@3 alone, which accepts field solver
versions 2 and 3). On the three free-offset composites of tests/field_solver_fixtures.py
(minimal, release and replacement, the last carrying cells.operator.scheduled_cell_replacement@1 and two
events), without stepping (the runs are test_field_solver_composite_runs.py):
1. a free-offset composite declares version 3 by default and is admitted: it binds the floor
   layout;
2. a held-bath composite is unchanged, and so is every composite world of the crossrev
   injection, volume, division and species sets and D150's fixtures (none has a free offset);
   a composite of any other inner model would stay outside the trigger;
3. "2" reproduces the legacy solver explicitly: the definition as built, and its own layout;
4. a checkpoint (here the start's) does not resume across a change of the declared solver,
   either way, directly or through a saved snapshot: validate_checkpoint refuses the other layout
   and branch_checkpoint the execution change, while the same branch without it is admitted.
"""

import jax
import pytest

from cells.definitions import pump_composite_spec as cs
from cells.definitions.specs import parse_spec
from cells.execution.state import initialise
from cells.numerics.surface_field import FACTORED_SOLVER_ID, FLOOR_SOLVER_ID, SPARSE_SOLVER_ID
from tests.field_solver_fixtures import (
    minimal,
    refused_across_the_change,
    release,
    replacement,
    with_solver,
)
from validation.tissue import field_solver_choice as choice
from validation.tissue import secreted_species_fixtures as fx

FREE = dict(minimal=minimal, release=release, replacement=replacement)


@pytest.fixture(scope="module", autouse=True)
def x64():
    jax.config.update("jax_enable_x64", True)


@pytest.mark.parametrize("name", sorted(FREE))
def test_a_free_offset_composite_declares_version_3_and_is_admitted(name):
    built = FREE[name]()
    assert built["model"]["id"] == cs.MODEL_ID and choice.in_family(built)
    laws = [op.get("law") or op.get("id") for op in built["model"]["operators"]]
    assert laws == (["cells.operator.scheduled_cell_replacement@1"] if name == "replacement" else [])
    assert choice.free_field_offsets(built) == 1
    assert built["execution"]["field_solver"] == FACTORED_SOLVER_ID
    auto = choice.declare(built)
    assert auto["execution"]["field_solver"] == FLOOR_SOLVER_ID
    assert choice.declare(built, "3") == auto
    assert with_solver(auto, FACTORED_SOLVER_ID) == built  # Nothing else differs.
    assert type(initialise(parse_spec(auto)).layout).__name__.endswith("FloorLayout")
    with pytest.raises(ValueError, match="no floor variant"):  # FR-17 stage 1: refused by name.
        choice.declare(with_solver(built, SPARSE_SOLVER_ID))


def held_bath_composites():
    from validation.division import division_crossrev
    from validation.tissue import composite_crossrev as crossrev
    from validation.tissue import secreted_species_crossrev as species

    out = dict(
        secreting_cell=fx.secreting_cell(),
        face_free=fx.face_free(),
        heredity_chain=fx.heredity_chain(secreted=True),
    )
    builders = dict(
        injection=crossrev.injection_worlds,
        volume=crossrev.volume_worlds,
        division=division_crossrev.division_worlds,
        species=species.species_worlds,
    )
    for set_name, build in builders.items():
        for name, value in build().items():
            raw = value if isinstance(value, dict) else next(v for v in value if "model" in v)
            out[f"{set_name}/{name}"] = raw
    return out


HELD = held_bath_composites()


@pytest.mark.parametrize("name", sorted(HELD))
def test_a_held_bath_composite_is_unchanged(name):
    raw = HELD[name]
    assert raw["model"]["id"] == cs.MODEL_ID and choice.in_family(raw)
    assert choice.free_field_offsets(raw) == 0
    assert choice.declare(raw) == raw


def test_a_composite_of_another_inner_model_is_outside_the_trigger():
    other = dict(model=dict(id=cs.MODEL_ID, inner_model="another_model@1"), execution={})
    assert not choice.in_family(other)
    assert choice.solver_for(other) is None  # It keeps what it declares (here nothing).


@pytest.mark.parametrize("name", sorted(FREE))
def test_the_legacy_solver_is_reproduced_explicitly(name):
    built = FREE[name]()
    legacy = choice.declare(built, "2")
    assert legacy == built and choice.solver_for(built, "2") == FACTORED_SOLVER_ID
    assert not type(initialise(parse_spec(legacy)).layout).__name__.endswith("FloorLayout")


@pytest.mark.parametrize("version", [FACTORED_SOLVER_ID, FLOOR_SOLVER_ID, SPARSE_SOLVER_ID])
def test_a_checkpoint_does_not_resume_across_a_solver_change(version, tmp_path):
    raw = with_solver(minimal(), version)
    refused_across_the_change(raw, initialise(parse_spec(raw)), tmp_path / "start")
