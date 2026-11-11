"""Path failure handling: PathNotConverged diagnostics and barrier-part isolation.

A point that cannot converge raises PathNotConverged with its stage diagnostics, and
the MG1 driver records such a path as a failed row (failed_paths, judged in B4)
without aborting the part; every path is also appended to barrier.cases.jsonl.
"""

from types import SimpleNamespace

import jax
import numpy as np
import pytest

from cells.analysis import mechanical_equilibrium as me
from validation.morphogenesis import mg1_vertex as d

jax.config.update("jax_enable_x64", True)


def test_unconverged_point_raises_with_diagnostics():
    pb, model = d._staddon_problem(4, 1.0, 3.7, seed=3)
    eq = me.minimize(pb)
    junction = d.orientation_junctions(model)[0]
    t = pb.host_topology
    tail, head = int(t.junction_tail[junction]), int(t.junction_head[junction])
    dvec = eq.position[head] + np.asarray(t.junction_image[junction]) @ pb.box.T - eq.position[tail]
    with pytest.raises(me.PathNotConverged) as caught:
        me._minimize_path(
            pb,
            junction,
            0.5 * float(np.linalg.norm(dvec)),
            eq.position,
            float(np.arctan2(dvec[1], dvec[0])),
            tolerance=1e-11,
            max_iterations=1,
        )
    assert isinstance(caught.value.diagnostics, dict)


def test_failed_path_is_recorded_and_counted(tmp_path, monkeypatch):
    original = me.contraction
    calls = {"n": 0}

    def flaky(pb, x, junction, fractions, **kw):
        calls["n"] += 1
        if calls["n"] == 2:
            raise me.PathNotConverged("forced for the test", {"stage": "test"})
        return original(pb, x, junction, fractions, **kw)

    monkeypatch.setattr(me, "contraction", flaky)
    args = SimpleNamespace(quick=True, output=tmp_path, registered=None, dry_run=False)
    result = d.part_barrier(args)
    failed = [row for row in result["rows"] if row["status"] == "failed"]
    assert len(failed) == 1 and result["metrics"]["failed_paths"] == 1
    assert failed[0]["diagnostics"] == {"stage": "test"}
    assert result["metrics"]["path_max_force"] is not None
    lines = (tmp_path / "barrier.cases.jsonl").read_text().splitlines()
    assert len(lines) == len(result["rows"])
