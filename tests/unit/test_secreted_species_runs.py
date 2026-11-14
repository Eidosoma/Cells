"""Compiled runs of the secreted-species operators (D150 version 1; design §7).

Species-only worlds (validation/tissue/secreted_species_fixtures), every one started from a
pre-formed profile (the lead's ruling 5), through the runner and its host checks:
* a cell producing and secreting into its node, which clears and leaks to the bath, with saturable
  uptake back: every host check passes on every row, at IMEX and in the face-free world under RK4;
* idle claim 2: zero rates, and operators declared with no routes, give every field, observation
  and diagnostic bitwise equal to the composition without the operators;
* restart before, at and after a founder's schedule change and a replacement event, in process and
  through a written snapshot, bitwise; the newcomer's rates (its template's, zero included) apply
  exactly from the event step;
* a vector-window batch with device checks mixing per-world rates, K_M, V_max and k_u: bitwise
  against the reversed batch and within 1e-12 of each field's scale against each world's own run.
A few minutes of compiles; the tier-1 smoke tests are test_species_turnover.py,
test_species_exchange.py and test_secreted_species.py.
"""

import copy

import jax
import numpy as np
import pytest

from cells.core.runner import run
from cells.core.specs import parse_spec
from validation.tissue import secreted_species_fixtures as fx

jax.config.update("jax_enable_x64", True)

DT = 1e-3
EVENT = 0.006


def secretion(
    end=0.02,
    *,
    produce=1e-4,
    export=0.1,
    clear=0.5,
    vmax=1e6,
    km=5e-4,
    ku=None,
    solver=fx.IMEX,
    dt=DT,
    faces=True,
):
    builder = fx.secreting_cell if faces else fx.face_free
    raw = builder(end=end, dt=dt, solver=solver, observation_times=fx.grid_times(end, dt, end / 4))
    raw = fx.with_turnover(
        raw,
        [("produce", "cell_0", "production"), ("clear", "ecs_0", "clearance")],
        [("produce", "cell_0", [(0.0, produce)]), ("clear", None, [(0.0, clear)])],
    )
    routes = [
        ("secrete", "contact_0", "export", "first_order"),
        ("sink", "contact_0", "import", "saturable"),
    ]
    controls = [("secrete", "cell_0", [(0.0, export)]), ("sink", "cell_0", [(0.0, vmax, km)])]
    if ku is not None:
        routes.append(("take_up", "contact_0", "import", "first_order"))
        controls.append(("take_up", "cell_0", [(0.0, ku)]))
    return fx.with_exchange(raw, routes, controls)


def same(a, b):
    return all(
        np.asarray(x).tobytes() == np.asarray(y).tobytes() for x, y in zip(a, b, strict=True)
    )


def test_a_species_only_world_closes_every_host_check():
    from cells.models.registry import get_model

    spec = parse_spec(secretion())
    result = run(spec)  # Host checks on every accepted row; raise on failure.
    h = result.history
    assert np.all(np.asarray(h.turnover_produced_fmol)[-1] >= 0)
    assert np.asarray(h.exchange_moved_fmol)[-1][0] > 0 > np.asarray(h.exchange_moved_fmol)[-1][1]
    assert np.asarray(h.turnover_outside_cleared_fmol)[-1].sum() > 0
    summary = get_model(spec.model).summarize(result.history, result.diagnostics, spec)
    assert summary["operators"] == [fx.TURNOVER, fx.EXCHANGE]
    assert summary["exchange_species"] == {fx.SPECIES: dict(catalogue=None, evidence=None)}


def test_the_face_free_world_closes_every_host_check_under_rk4():
    """RK4 is guarded, not refused (§4.2): exact half-steps around @3's RK4 step, whose energy bound
    is the absolute 2e-8 pJ, in the face-free world of the operators' work."""
    spec = parse_spec(
        secretion(
            end=0.002, dt=1e-4, solver="rk4", faces=False, produce=1e-3, export=5.0, clear=2.0
        )
    )
    result = run(spec)
    assert result.diagnostics["max_energy_balance_error_pJ"] < 2e-8


def without_operators(raw):
    plain = copy.deepcopy(raw)
    plain["model"]["operators"] = []
    for key in ("turnover_controls", "exchange_controls"):
        del plain["experiment"][key]
    return plain


def test_idle_operators_equal_the_composition_without_them():
    raw = secretion(produce=0.0, export=0.0, clear=0.0, vmax=0.0)
    plain = run(parse_spec(without_operators(raw)))
    idle = run(parse_spec(raw))
    for name in type(plain.history)._fields:
        assert np.array_equal(
            np.asarray(getattr(idle.history, name)), np.asarray(getattr(plain.history, name))
        ), name
    for name, value in vars(plain.observations).items():
        assert np.array_equal(np.asarray(getattr(idle.observations, name)), np.asarray(value)), name
    for name, value in plain.diagnostics.items():
        assert idle.diagnostics[name] == value, name
    empty = copy.deepcopy(raw)
    for block in empty["model"]["operators"]:
        block["routes"] = []
    empty["experiment"]["turnover_controls"] = []
    empty["experiment"]["exchange_controls"] = []
    routeless = run(parse_spec(empty))
    for name in type(plain.history)._fields:
        assert np.array_equal(
            np.asarray(getattr(routeless.history, name)), np.asarray(getattr(plain.history, name))
        ), name


def swapped(template_rate):
    """Two cells; cell_0's founder changes its export rate at 3 ms, then is replaced at 6 ms by a
    newcomer whose template declares template_rate."""
    end = 0.01
    base = fx.world(
        cells=(("cell_0", 1.0), ("cell_1", 1.0)),
        nodes=(("ecs_0", 1.0), ("ecs_1", 1.0)),
        contacts=(("contact_0", "cell_0", "ecs_0"), ("contact_1", "cell_1", "ecs_1")),
        faces=(("face_0", "ecs_0", "bath", 1e-10, 1e-5), ("face_1", "ecs_1", "bath", 1e-10, 1e-5)),
        junctions=(("junction_0", "cell_0", "cell_1"),),
        end=end,
        observation_times=[0.0, 0.003, EVENT, 0.008, end],
        concentrations_mM=dict(cell_0=1e-3, cell_1=1e-3, ecs_0=5e-4, ecs_1=5e-4),
    )
    template = fx.template(base, "cell_0", "T", s_mM=1.2e-3)
    raw = fx.with_replacement(base, [template], [(EVENT, "cell_0", "T", "c0_new")])
    return fx.with_exchange(
        raw,
        [
            ("sec_0", "contact_0", "export", "first_order"),
            ("sec_1", "contact_1", "export", "first_order"),
        ],
        [("sec_0", "cell_0", [(0.0, 0.2), (0.003, 0.15)]), ("sec_1", "cell_1", [(0.0, 0.2)])],
        templates=[("T", {"sec_0": {"rate": template_rate}})],
    )


@pytest.mark.parametrize("template_rate", [0.1, 0.0])
def test_restart_across_a_schedule_change_and_an_event_is_bitwise(tmp_path, template_rate):
    from cells.io import load_snapshot, write_snapshot

    spec = parse_spec(swapped(template_rate))
    result = run(spec)
    moved = np.asarray(result.history.exchange_moved_fmol)[:, 0]
    k = int(round(EVENT / DT))
    if template_rate == 0.0:  # The founder's rate never applies after the event step.
        assert np.all(moved[k + 1 :] == moved[k]) and moved[k] > moved[k - 1]
    for t in (0.002, 0.003, EVENT, 0.008):
        checkpoint = result.checkpoint_at(t)
        resumed = run(spec, checkpoint)
        for a, b in zip(resumed.history, result.history, strict=True):
            assert np.array_equal(np.asarray(a), np.asarray(b)[checkpoint.step_index :]), t
    checkpoint = result.checkpoint_at(EVENT)
    write_snapshot(tmp_path / "checkpoint", result.spec, checkpoint)
    loaded = load_snapshot(tmp_path / "checkpoint")
    again = run(loaded.spec, loaded.checkpoint)
    for a, b in zip(again.history, result.history, strict=True):
        assert np.array_equal(np.asarray(a), np.asarray(b)[checkpoint.step_index :])


def test_a_vector_batch_mixes_per_world_rates_and_law_parameters():
    from cells.core.batch import BatchSpec, WorldSpec
    from cells.core.vector_windows import run_vector_windowed
    from cells.core.windows import WindowPolicy

    specs = [
        parse_spec(secretion(export=0.1, vmax=1e6, km=5e-4, ku=1e-6)),
        parse_spec(secretion(export=0.3, vmax=3e6, km=1e-3, ku=3e-6, produce=2e-4)),
        parse_spec(secretion(export=0.05, vmax=5e5, km=2e-4, ku=2e-6, clear=1.0)),
    ]

    def batch(order):
        worlds = tuple(WorldSpec(i + 1, specs[j]) for i, j in enumerate(order))
        return run_vector_windowed(
            BatchSpec(worlds, len(worlds), 10**6, 2**31), WindowPolicy(4, "checkpoints")
        )

    forward, backward = batch([0, 1, 2]), batch([2, 1, 0])
    for k, spec in enumerate(specs):
        final = forward.worlds[k + 1].final.state
        assert same(final, backward.worlds[3 - k].final.state)
        single = run(spec).history
        for name in type(final)._fields:
            a, b = np.asarray(getattr(final, name)), np.asarray(getattr(single, name))[-1]
            scale = np.max(np.abs(b), initial=0.0)
            if name.endswith("_work_pJ"):  # Differences of free energies: their magnitudes.
                partner = name.replace("_work_pJ", "_energy_magnitude_pJ")
                if hasattr(single, partner):
                    scale = max(scale, np.max(np.asarray(getattr(single, partner))[-1]))
            assert np.max(np.abs(a - b), initial=0.0) <= 1e-12 * scale + 1e-30, (k, name)
