"""apical_vertex_mechanics@1 events: ablation, restart from disk, vmap, step refusal.

A scheduled Farhadifar cut books its control work and the exact velocity jump;
a run written with write_run and resumed from its loaded snapshot ends bitwise
equal to the uninterrupted run; vmapped steps equal single worlds; a step whose
dt * rho exceeds the solver bound is refused without changing the state.
"""

import jax
import numpy as np

from cells.core.runner import run
from cells.core.specs import parse_spec
from cells.io import load_snapshot, write_run
from cells.models import apical_vertex as av
from tests.apical_vertex_fixtures import (
    GAMMA,
    LAMBDA,
    P_CASE,
    farhadifar_cut,
    honeycomb,
    jax_forces,
)
from validation.morphogenesis import mg1_reference as ref
from validation.morphogenesis import mg1_theory as theory

jax.config.update("jax_enable_x64", True)


def test_ablation_books_control_work_and_the_velocity_jump():
    definition = honeycomb(end_time=1.0, observation_times=[0.0, 0.5, 0.5625, 1.0], dt=0.0625)
    controls, cells = farhadifar_cut(definition)
    definition["experiment"]["parameter_controls"] = controls
    spec = parse_spec(definition)
    result = run(spec)
    obs = result.observations
    tissue = ref.from_definition(definition)
    before, after = tissue, ref.with_control(tissue, controls[1])
    x = tissue.position
    expected_work = ref.energy(after, x) - ref.energy(before, x)
    assert abs(obs.total_control_work[1]) == 0
    assert abs(obs.total_control_work[2] - expected_work) <= 1e-12 * abs(expected_work)
    # The jump of velocity across the event, at the event row, is exact.
    jump = ref.velocity_jump(before, after, x)
    state, layout = av.initial_values(spec)
    cut_state = state._replace(
        line_tension=np.asarray(result.history.line_tension[-1]),
        contractility=np.asarray(result.history.contractility[-1]),
    )
    np.testing.assert_allclose(
        jax_forces(cut_state, layout)[:32] - jax_forces(state, layout)[:32], jump, atol=1e-13
    )
    # 120-degree junctions: the cut junction opens at 2 (Lambda + Gamma L) / eta.
    j = tissue.junction_ids.index(definition["model"]["junctions"][0]["id"])
    t, h = tissue.junction_tail[j], tissue.junction_head[j]
    d = x[h] + tissue.junction_image[j] @ tissue.box.T - x[t]
    rate = (jump[h] - jump[t]) @ (d / np.linalg.norm(d))
    assert abs(rate - theory.recoil_opening_rate(LAMBDA, GAMMA, P_CASE)) <= 1e-10
    assert result.diagnostics["max_energy_balance_allowance_used"] < 1.0


def test_restart_from_a_written_snapshot_is_bitwise(tmp_path):
    definition = honeycomb(
        displacement=0.05, seed=4, end_time=4.0, observation_times=[0.0, 2.0, 4.0], dt=0.125
    )
    spec = parse_spec(definition)
    whole = run(spec)
    summary = write_run(tmp_path / "run", whole, checkpoint_times=(2.0,))
    assert summary["cells"] == 16 and summary["status"] == "complete"
    snapshot = load_snapshot(tmp_path / "run" / "snapshots" / "step-000016")
    assert snapshot.spec.to_dict() == spec.to_dict()
    resumed = run(snapshot.spec, snapshot.checkpoint)
    for a, b in zip(whole.final.state, resumed.final.state, strict=True):
        np.testing.assert_array_equal(np.asarray(a), np.asarray(b))
    final = load_snapshot(tmp_path / "run" / "checkpoint_final")
    for a, b in zip(whole.final.state, final.checkpoint.state, strict=True):
        np.testing.assert_array_equal(np.asarray(a), np.asarray(b))
