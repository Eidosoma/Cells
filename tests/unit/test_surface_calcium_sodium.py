"""Initial sodium/calcium composition checks, separate from full qualification.

These checks exercise species ownership, static catalog routing, old-model
reductions, short compiled execution and saved/report identity. Full 2-ms
trajectories, refinement, assembly dynamics and world replay remain required.
"""

import jax
import numpy as np
import pytest

from cells.core.runner import run, timeline
from cells.core.schedule import control_values
from cells.core.specs import ConfigError, parse_spec
from cells.ensemble import ionic
from cells.io import load_snapshot, write_run
from cells.models import surface_calcium_channels as prior
from cells.models import surface_calcium_sodium as model
from cells.models import surface_kinetic
from cells.models.registry import get_model
from cells.processes import sodium_channels
from tests.unit import test_surface_calcium as shared
from tests.unit.test_surface_kinetic import assert_states, exact
from validation.tissue import surface_calcium_channel_fixtures as prior_fixtures
from validation.tissue import surface_calcium_reference as reference
from validation.tissue import surface_calcium_sodium_fixtures as fixtures

BACKEND, EVIDENCE = shared.BACKEND, shared.EVIDENCE
PREFIX = "resolved-calcium-sodium"


@pytest.fixture(scope="module", autouse=True)
def composition_context():
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(shared, "model", model)
        patch.setattr(shared, "fixtures", fixtures)
        patch.setattr(shared, "PREFIX", PREFIX)
        yield


def evidence(name, value):
    shared.evidence(PREFIX + "-" + name, value)


def initial(raw=None):
    spec = parse_spec(fixtures.definition() if raw is None else raw)
    state, layout = model.initial_values(spec)
    controls = control_values(spec, [0.0])
    return spec, state, layout, type(controls)(*(v[0] for v in controls))


def test_identity_catalogs_and_rejections():
    for backend in ("cpu", "gpu"):
        raw = fixtures.definition(backend=backend)
        spec, state, p, _ = initial(raw)
        assert parse_spec(spec.to_dict()) == spec
        assert get_model(spec.model) is model and type(p) is model.LAYOUT_TYPE
        assert spec.to_dict()["model"]["id"] == "resolved_calcium@3"
        assert spec.to_dict()["model"]["ionic"]["id"] == "resolved_tissue@4"
        assert (
            ionic.parse_spec(dict(model="ionic_worlds@1", simulation=raw, worlds=2)).simulation
            == spec
        )
        np.testing.assert_array_equal(p.channel_laws, [0, 1, 0, 1, 1, 2, 2, 0])
        view = model.ionic_layout(state, p, xp=np)
        assert type(view) is surface_kinetic.SODIUM_OWNED_VIEW_TYPE
        assert surface_kinetic.channel_process(view) is sodium_channels
        np.testing.assert_array_equal(view.cytosol_amount, model.cytosol_amount(state, p, xp=np))
        assert len(model.STATE_TYPE._fields) == 34
        for index, code in ((5, 3), (7, 2)):
            laws = p.channel_laws.copy()
            laws[index] = code
            assert not model.domain_valid(state, p._replace(channel_laws=laws), p.active, xp=np)
    faults = ("outer", "inner", "old_catalog", "species", "step", "capacity", "control")
    for fault in faults:
        raw = fixtures.definition()
        m, x = raw["model"], raw["execution"]
        if fault == "outer":
            m["id"] = "resolved_calcium@2"
        elif fault == "inner":
            m["ionic"]["id"] = "resolved_tissue@3"
        elif fault == "old_catalog":
            m["id"], m["ionic"]["id"] = "resolved_calcium@2", "resolved_tissue@3"
        elif fault == "species":
            m["ionic"]["channels"][5]["species_id"] = "K"
        elif fault == "step":
            x["dt"] = 5e-6
        elif fault == "capacity":
            x["channel_capacity"] = 6
        else:
            raw["experiment"]["channel_controls"][5]["schedule"][0]["availability"] = -0.1
        with pytest.raises(ConfigError):
            timeline(parse_spec(raw))
    evidence("design", dict(status="passed", rejected=list(faults), inputs=spec.to_dict()))


test_independent_stage_rates_and_accounting = shared.test_independent_stage_rates_and_accounting


def test_free_sodium_ownership_and_block():
    spec, state, p, control = initial()
    changed = model.STATE_TYPE(*(np.array(v) for v in state))
    names = [s.id for s in spec.model.stores[0].species]
    na = names.index("Na")
    cy, er = int(p.er_cytosol[0]), int(p.er_er[0])
    changed.chemical_amount_increment[0, na, [cy, er]] += 1e-4 * np.array([-1, 1])
    assert model.domain_valid(changed, p, p.active, xp=np)
    exact(model.ensemble_voltage(state, p, spec, 0), model.ensemble_voltage(changed, p, spec, 0))
    before, after = (model.readouts(y, control, p, xp=np) for y in (state, changed))
    assert after.derivative.channel_transferred[5] != before.derivative.channel_transferred[5]
    np.testing.assert_allclose(
        after.derivative.channel_transferred[[0, 1, 2, 3, 4, 6]],
        before.derivative.channel_transferred[[0, 1, 2, 3, 4, 6]],
        rtol=3e-10,
        atol=3e-12,
    )
    blocked = control._replace(channel=control.channel.copy())
    blocked.channel[5] = 0.0
    stopped = model.readouts(state, blocked, p, xp=np)
    assert before.derivative.channel_transferred[5] != 0
    assert stopped.derivative.channel_transferred[5] == 0
    exact(stopped.derivative.channel_gate, before.derivative.channel_gate)
    np.testing.assert_array_equal(
        stopped.derivative.channel_transferred[[0, 1, 2, 3, 4, 6]],
        before.derivative.channel_transferred[[0, 1, 2, 3, 4, 6]],
    )
    c = reference.bind(spec.to_dict())
    expected, _, proof = reference.evaluate(c, reference.flatten(c, changed._asdict()), 0.0)
    ratio = assert_states(
        c,
        reference.flatten(c, after.derivative._asdict()),
        expected,
        atol=3e-12,
        charge_atol=3e-23,
        rtol=3e-10,
    )
    evidence(
        "ownership",
        dict(
            status="passed",
            internal_sodium_transfer_fmol=1e-4,
            max_error_over_budget=ratio,
            independent_root=proof,
            unchanged_plasma_voltage=True,
            selected_population_blocked=5,
        ),
    )


def test_previous_potassium_calcium_reduction():
    raw = prior_fixtures.definition()
    old, state, p, control = initial(raw)
    assert get_model(old.model) is prior and type(p) is prior.LAYOUT_TYPE
    raw["model"]["id"], raw["model"]["ionic"]["id"] = "resolved_calcium@3", "resolved_tissue@4"
    raw["execution"]["dt"] = fixtures.definition()["execution"]["dt"]
    new, newer, q, held = initial(raw)
    exact(state, newer)
    first, second = prior.readouts(state, control, p, xp=np), model.readouts(newer, held, q, xp=np)
    exact(first.derivative, second.derivative)
    exact(jax.tree.leaves(first.field), jax.tree.leaves(second.field))
    assert parse_spec(old.to_dict()) == old and parse_spec(new.to_dict()) == new
    evidence(
        "legacy",
        dict(status="passed", potassium_only_initial_rates="bitwise", old_catalog_preserved=True),
    )


def test_initial_assembly_report_and_planning():
    spec = shared.parse_assembly(fixtures.assembly_definition(backend=BACKEND))
    state = shared.assembly.initial_state(spec)
    report = shared.assembly.summary(spec, state) | {"execute_seconds": 0.0}
    shared.test_assembly_aggregation_retains_owned_ligand((spec, state, report))
    shared.test_sixteen_gpu_planning_keeps_worlds_and_model()
    evidence(
        "assembly-wiring",
        dict(
            status="passed",
            physical_model=report["physical_model"],
            checked=[
                "owned calcium/IP3 reporting",
                "missing-section rejection",
                "local 16-GPU planning",
            ],
            scope="Initial-state and planning only; no assembly dynamics or remote execution",
        ),
    )


def test_compiled_smoke_reference_and_checkpoint(tmp_path):
    raw = fixtures.definition(backend=BACKEND)
    raw["experiment"].update(end_time=50e-6, observation_times=[0.0, 25e-6, 50e-6])
    value = run(parse_spec(raw))
    assert all(v.device.platform == BACKEND for v in value.final.state)
    c = reference.bind(value.spec.to_dict())
    expected = reference.integrate(value.spec.to_dict())
    ratio = assert_states(
        c, reference.flatten(c, vars(value.observations)), np.asarray(expected["state"])
    )
    write_run(tmp_path / "smoke", value)
    loaded = load_snapshot(tmp_path / "smoke/checkpoint_final")
    exact(loaded.checkpoint.state, value.final.state)
    assert loaded.spec == value.spec and type(loaded.checkpoint.layout) is model.LAYOUT_TYPE
    summary = model.summarize(value.history, value.diagnostics, value.spec)
    assert summary["model"] == model.MODEL_ID
    assert summary["channel_laws"] == {ch.id: ch.kinetic_law for ch in value.spec.model.channels}
    evidence(
        "smoke",
        dict(
            status="passed",
            inputs=value.spec.to_dict(),
            diagnostics=value.diagnostics,
            max_error_over_budget=ratio,
            independent_reference=expected,
            scope="50-us trajectory and checkpoint round trip; full qualification pending",
        ),
    )
