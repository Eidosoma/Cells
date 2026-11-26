"""The adapter for the engine's record layout (FORMAT.md, cells.model.assembly_lineages@1).

Planted controls: a transfer constant that disagrees with k_join/k_leave, and SSA prose
the oracle does not know. Both must be refused rather than read.
"""

from __future__ import annotations

import numpy as np
import pytest

from validation.gard.references import ssa_oracle as so
from validation.gard.references.records import RecordFormatError, adapt_run, adapt_world


def _world(K=100.0, with_beta=True):
    G = 3
    w = {"types": {"count": G, "prefix": "t", "transfer_constant": K}, "supply": 0.01,
         "exchange": {"law": "cells.exchange.reservoir_exchange@1", "leave_rate": 1e-4}, "founder": [1, 0, 2],
         "fission": {"operator": "cells.operator.size_threshold_fission@1", "size": 80,
                     "partition": {"rule": "exact_fraction", "fraction": 0.5}},
         "continuation": {"operator": "cells.operator.daughter_continuation@1", "daughter": "first", "empty": "extinct",
                          "sink": "discard"},
         "units": {"time": "nominal", "temperature_K": None}}
    if with_beta:
        w["law_data"] = {"catalysis_matrix": [[1.0, 0.5, 0.0], [0.0, 2.0, 0.1], [0.3, 0.0, 0.0]]}
    return {"format": "cells.assembly_lineages.world@1", "id": "abc", "world": w,
            "derived": {"types": ["t0", "t1", "t2"], "join_rate": [0.01] * G, "leave_rate": [1e-4] * G,
                        "standard_transfer_mu_RT": [-4.605170185988092] * G, "founder_size": 3}}


def _run(**ssa_over):
    ssa = {"tau": "tau = -ln(u1) / a0", "channel": "the first j with c_j > min(u2 * a0, nextafter(a0, 0))",
           "prefix": "serial left fold in channel order: c_0 = a_0, c_j = c_(j-1) + a_j; a0 = c_(2C-1)"}
    ssa.update(ssa_over)
    return {
        "world": "abc",
        "founder": "world",
        "mode": "single_lineage",
        "law": {
            "id": "cells.rate_factor.gard_catalysis_pair_consistent@1",
            "form": "pair-consistent",
            "energy_role": "passive",
            "check": {"admitted_as": "passive"},
        },
        "stream": {
            "seed": 1,
            "branch": 0,
            "uniform": "u = (m + 1/2) * 2**-52, m the low 52 bits of one 64-bit Threefry word",
        },
        "ssa": ssa,
        "ledger": {"event_heat": "q = ..."},
        "channels": {"rows": []},
        "end": {"status": "complete", "time": 1.0},
        "time": {"unit": "nominal"},
    }


def test_engine_world_maps_onto_the_canonical_view():
    v = adapt_world(_world(), "world.json", {"experiment": {"growth_event_limit": 40000}})
    assert v.n_types == 3 and v.fission_mass == 80 and v.partition == "exact_fraction"
    assert np.allclose(v.rho, 0.01) and np.allclose(v.k_join / v.k_leave, 100.0)
    assert v.event_guard == 40000 and v.guard_rule == "stop" and v.continuation == "first"
    assert v.beta[1, 1] == 2.0
    no_cat = adapt_world(_world(with_beta=False), "world.json")
    assert np.all(no_cat.beta == 0)  # the exchange law alone


def test_a_transfer_constant_that_disagrees_is_refused():
    with pytest.raises(RecordFormatError):
        adapt_world(_world(K=101.0), "world.json")


def test_engine_run_prose_maps_to_tokens_and_unknown_prose_is_refused():
    r = adapt_run(_run(), "run.json")
    assert so.SSAConvention.from_declared(r.ssa_convention)
    assert r.check_verdict == "passive" and r.form == "pair-consistent" and r.t_end == 1.0
    odd = adapt_run(_run(tau="tau = -ln(1 - u1) / a0"), "run.json")
    with pytest.raises(so.ConventionMissing):
        so.SSAConvention.from_declared(odd.ssa_convention)
    unfolded = adapt_run(_run(prefix="pairwise sum"), "run.json")
    with pytest.raises(so.ConventionMissing):
        so.SSAConvention.from_declared(unfolded.ssa_convention)


def test_a_probe_whose_npz_differs_from_its_declared_hash_is_refused(tmp_path):
    import hashlib
    import json as _json
    from validation.gard.references import engine_layout
    d = tmp_path / "probe"
    d.mkdir()
    np.savez(d / "probe.npz", similarity=np.array([0.5]))
    digest = hashlib.sha256((d / "probe.npz").read_bytes()).hexdigest()
    (d / "probe.json").write_text(_json.dumps({"arrays_sha256": digest}))
    engine_layout.load_engine_probe(d)
    np.savez(d / "probe.npz", similarity=np.array([0.6]))  # planted: outputs changed after the hash
    with pytest.raises(RecordFormatError):
        engine_layout.load_engine_probe(d)


def test_an_ensemble_run_on_another_design_is_refused(tmp_path):
    import json as _json
    from validation.gard.references import harness
    d = tmp_path / "ens"
    d.mkdir()
    design = harness.ensemble_design_record()
    design["runs"] = 200  # planted: a design other than the registered one
    (d / "beta0_ensemble_design.json").write_text(_json.dumps(design))
    (d / "beta0_ensemble.json").write_text(_json.dumps({"members": {}}))
    report = harness.run_rows({"beta0_ensemble": str(d)}, rows=[1])
    assert report["status"] == 2 and "registered design" in report["rows"]["1"]["error"]
