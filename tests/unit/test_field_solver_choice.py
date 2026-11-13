"""D147's field solver choice in the drivers (validation/tissue/field_solver_choice.py).

A world with free field offsets, the W1 hold's full tissue as heredity_pilot builds it,
declares version 3 by default and version 2 when "2" is chosen; "2" reproduces the
definition made before D147. Worlds without free offsets are unchanged by default: the
hold's held-bath start graph, the sheet70 disc sheet, W1's trajectories, W2's arms, G2-Q1's
cases and W37. The scale world's own default stays version 2, so its other callers (the
825-node guard worlds, the studies) are unchanged.
"""

import numpy as np
import pytest

from cells.numerics.surface_field import FACTORED_SOLVER_ID, FLOOR_SOLVER_ID
from validation.tissue import field_solver_choice as choice
from validation.tissue import heredity_pilot as pilot
from validation.tissue import resolved_scale_world as scale_world


@pytest.fixture(scope="module")
def tissue():
    return pilot.Tissue()


def synthetic_start(tissue):
    """A start record of part_start's shape at the base definition's own composition."""
    base = pilot.heredity.tissue_definition(dt=pilot.DT, end_time=0.01)
    cell = base["model"]["cells"][0]["initial_amount_fmol"]
    species = list(cell)
    gates = {c["id"].split("_")[0]: c["initial_gate"] for c in base["model"]["channels"]}
    return dict(
        species=np.array(species),
        amounts_fmol=np.tile([cell[k] for k in species], (tissue.cells, 1)),
        kir_gate=np.tile(gates["kir"], (tissue.cells, 1)),
        nav_gate=np.tile(gates["nav"], (tissue.cells, 1)),
        junction_gate=np.ones(len(tissue.pairs)),
    )


def full_tissue(tissue, field_solver):
    return pilot.tissue_world(
        tissue, 2, 1.0, synthetic_start(tissue), end_step=10, observed=[0, 10],
        backend="cpu", field_solver=field_solver,
    )  # fmt: skip


def test_the_full_tissue_declares_version_3_by_default_and_2_when_chosen(tissue):
    auto, two, three = (full_tissue(tissue, c) for c in ("auto", "2", "3"))
    assert choice.free_field_offsets(two) == 172
    assert auto["execution"]["field_solver"] == FLOOR_SOLVER_ID
    assert three == auto
    assert two["execution"]["field_solver"] == FACTORED_SOLVER_ID
    two["execution"]["field_solver"] = FLOOR_SOLVER_ID  # Nothing else differs.
    assert two == auto


def test_the_pilot_option_defaults_to_d147(monkeypatch, tmp_path):
    seen = []
    monkeypatch.setitem(pilot.PARTS, "start", lambda args: seen.append(args.field_solver))
    pilot.main(["start", "--output", str(tmp_path)])
    pilot.main(["start", "--output", str(tmp_path), "--field-solver", "2"])
    assert seen == ["auto", "2"]


def test_the_scale_world_default_is_unchanged():
    default = scale_world.definition()
    assert default["execution"]["field_solver"] == FACTORED_SOLVER_ID
    three = scale_world.definition(field_solver=FLOOR_SOLVER_ID)
    assert three["execution"]["field_solver"] == FLOOR_SOLVER_ID
    three["execution"]["field_solver"] = FACTORED_SOLVER_ID
    assert three == default


def no_offset_worlds():
    from validation.tissue import composite_crossrev as crossrev

    tissue = pilot.Tissue()
    out = {
        "held_bath_start": pilot.held_bath_definition(tissue, 2, 1.0),
        "sheet70_disc37": pilot.long_sheet_definition(37, 1.0, pilot.DT, 5.0, "cpu")[0],
        "sheet70_disc19": pilot.long_sheet_definition(19, 0.6, pilot.DT, 5.0, "cpu")[0],
    }
    for name, raw in crossrev.qualification_worlds().items():
        if name.startswith(("W1_", "W2_", "G2_", "W37")):
            out[name] = raw
    return out


WORLDS = no_offset_worlds()


@pytest.mark.parametrize("name", sorted(WORLDS))
def test_worlds_without_free_offsets_are_unchanged_by_default(name):
    raw = WORLDS[name]
    assert choice.free_field_offsets(raw) == 0
    assert choice.declare(raw, "auto") == raw


def test_an_unknown_choice_is_refused():
    with pytest.raises(ValueError, match="field solver choice"):
        choice.solver_for(scale_world.definition(), "4")
