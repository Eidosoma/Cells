"""Check cells.binding.rapid_binding@1 one-site occupancy against independent S1 states."""

import json

import jax
import jax.numpy as jnp
import numpy as np

from cells.definitions.specs import parse_spec
from cells.kinds import proton_buffer
from cells.laws.reactions import rapid_binding
from tests.unit import test_rapid_binding_kernel as fixture
from tests.unit.test_proton_buffer_kind import host
from tests.unit.test_rapid_binding_world import amounts, reference_cell


def compare():
    ligands, binders, _, net = fixture.system("S1")
    total_l, total_b = fixture.totals("S1", ligands, binders)
    held, comp_l, comp_b = fixture.masks(net, total_l.shape[1])
    kd = fixture.one_step_k(binders, ligands[0])
    assert net["path"] == "b4" and ligands == ("H",) and binders == ("buf1",)

    @jax.jit
    def solve(tl, tb):
        args = net["log_beta"], net["counts"], net["present"]
        u, valid = rapid_binding.free_ligands(
            tl, tb, *args, held, comp_l, comp_b, kd, path=net["path"], xp=jnp
        )
        free, forms = rapid_binding.speciation(u, tb, *args, xp=jnp)
        return free[0], forms[0, 1] / tb[0], valid

    free, occupancy, valid = map(np.asarray, solve(total_l, total_b))
    assert valid.all() and occupancy.dtype == np.float64
    states = fixture.VALUES["systems"]["S1"]["states"]
    ref_free = np.array([s["x_mM"]["H"] for s in states])
    ref_bound = np.array([s["forms_mM"]["buf1"]["buf1_H"] for s in states])
    ref_fraction = ref_bound / total_b[0]
    floors = [s["floor_residual_1e-13"] for s in states]
    free_tol = 2 * np.array([s["x"]["H"] for s in floors])
    bound_tol = 2 * np.array([s["forms"]["buf1|buf1_H"] for s in floors])
    # Dividing by the same binder total preserves the registered log-concentration tolerance.
    formula = free / (kd[0] + free)
    for value in (occupancy, formula):
        np.testing.assert_array_less(np.abs(np.log(value / ref_fraction)), bound_tol)
    np.testing.assert_array_less(np.abs(np.log(free / ref_free)), free_tol)
    wrong = total_l[0] / (kd[0] + total_l[0])
    missed = int(np.count_nonzero(np.abs(np.log(wrong / ref_fraction)) > bound_tol))
    assert missed > 0

    # Read the free base from the initialized tissue and recover the occupied fraction.
    raw, _ = reference_cell("S1", 0)
    spec = parse_spec(raw)
    _, state, params, _ = host(spec)
    read, ok = proton_buffer.stage_read(state, params, xp=np)
    assert ok
    row = list(spec.model.species_ids).index("buf1")
    tissue_fraction = 1 - amounts(read, params)[row, 0] / amounts(state, params)[row, 0]
    assert abs(np.log(tissue_fraction / ref_fraction[0])) < bound_tol[0]
    return {
        "states": len(states),
        "kd_mM": float(kd[0]),
        "max_fraction_error_vs_reference": float(np.max(np.abs(occupancy - ref_fraction))),
        "max_fraction_error_vs_formula": float(np.max(np.abs(occupancy - formula))),
        "fraction_range": [float(occupancy.min()), float(occupancy.max())],
        "total_ligand_control_failures": missed,
        "tissue": {"model": raw["model"]["id"], "state": 0, "fraction": float(tissue_fraction)},
    }


if __name__ == "__main__":
    jax.config.update("jax_enable_x64", True)
    with jax.default_device(jax.devices("cpu")[0]):
        print(json.dumps(compare(), indent=2, allow_nan=False))
