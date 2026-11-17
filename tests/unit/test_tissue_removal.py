"""Stable identities, explicit removed material, native source limits and CPU gathers."""

import json
import os
from pathlib import Path

import numpy as np
import pytest

from cells.processes import tissue_removal as cut
from validation.topology import betse_tissue_cut_reference as reference

ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = json.loads((ROOT / "validation/topology/betse_tissue_cut_protocol.json").read_text())


def evidence(name, record):
    if directory := os.environ.get("CELLS_COMPONENT_EVIDENCE"):
        root = Path(directory)
        root.mkdir(parents=True, exist_ok=True)
        (root / ("tissue-cut-" + name + ".json")).write_text(
            json.dumps(record, indent=2, allow_nan=False) + "\n"
        )


def native(name="cut-middle"):
    directory = os.environ.get("CELLS_BETSE_CUT_NATIVE_CAPTURE")
    if not directory:
        pytest.skip("Bounded runner supplies authenticated native cut captures")
    return json.loads((Path(directory) / (name + ".json")).read_text())


def sample():
    raw = native()
    return cut.topology_from_dict(raw["before"]["topology"]), raw


def fields(raw):
    before = raw["before"]
    nc = len(before["topology"]["cell_ids"])
    ne = len(before["topology"]["edge_ids"])
    volume = np.array(before["cells"]["cell_vol"]) * 1e15
    return {
        "ions": cut.OwnedField(
            np.array(before["sim"]["cc_cells"]),
            "cell",
            kind="density",
            units="mM",
            measure=volume,
            quantity_units="fmol",
            nonnegative=True,
        ),
        "water": cut.OwnedField(volume, "cell", kind="quantity", units="pL", nonnegative=True),
        "charge": cut.OwnedField(
            np.array([0.1, -0.2, 0.3]) * 1e-12, "cell", kind="quantity", units="C"
        ),
        "gates": cut.OwnedField(np.array(before["sim"]["mem_gate"]), "membrane", units="1"),
        "surface": cut.OwnedField(
            np.arange(1.0, len(before["topology"]["membrane_ids"]) + 1) * 1e10,
            "membrane",
            kind="density",
            units="molecules/m2",
            measure=np.array(before["cells"]["mem_sa"]),
            quantity_units="molecules",
            nonnegative=True,
        ),
        "edge_work": cut.OwnedField(
            np.linspace(-0.3, 0.7, ne), "edge", kind="quantity", units="pJ"
        ),
        "environment": cut.OwnedField(
            np.array(before["sim"]["cc_env"]),
            "environment",
            kind="density",
            units="mM",
            measure=np.array(before["cells"]["true_ecm_vol"]) * 1e15,
            quantity_units="fmol",
            nonnegative=True,
        ),
        "global_equal_cell_count": cut.OwnedField(
            np.arange(nc, dtype=np.int64), "global", axis=None
        ),
        "cell_flags": cut.OwnedField(np.array([True, False, True]), "cell", axis=0),
    }


def reference_field(field):
    return dict(
        values=np.asarray(field.values).tolist(),
        shape=list(np.shape(field.values)),
        domain=field.domain,
        axis=field.axis,
        kind=field.kind,
        measure=None if field.measure is None else np.asarray(field.measure).tolist(),
        replacement_measure=None
        if field.replacement_measure is None
        else np.asarray(field.replacement_measure).tolist(),
        amount_scale=float(field.amount_scale),
    )


def check_field(field, actual, expected):
    atol = 3e-22 if field.units == "C" else 2e-12
    for key, value in actual._asdict().items():
        if value is None:
            assert expected[key] is None
            continue
        wanted = np.asarray(expected[key]).reshape(np.shape(value))
        if key in ("retained", "removed_values") and field.replacement_measure is None:
            np.testing.assert_array_equal(value, wanted)
        else:
            np.testing.assert_allclose(value, wanted, rtol=5e-12, atol=atol)
    assert actual.retained.dtype == np.asarray(field.values).dtype
    if actual.balance_residual is not None:
        np.testing.assert_allclose(actual.balance_residual, 0, rtol=0, atol=atol)


def chain(count):
    contacts = max(0, count - 1)
    cells = [(i, i + 1) for i in range(contacts)]
    membranes = [(2 * i + 1, 2 * (i + 1)) for i in range(contacts)]
    roles = [True] * contacts
    if count >= 3:
        cells.append((count - 1, 0))
        membranes.append((-1, -1))
        roles.append(False)
    return cut.validate_topology(
        cut.Topology(
            tuple(f"c{i}" for i in range(count)),
            tuple(f"m{i}" for i in range(2 * count)),
            tuple(f"e{i}" for i in range(len(cells))),
            ("env",),
            np.repeat(np.arange(count), 2),
            np.zeros(2 * count, int),
            np.asarray(cells, int).reshape(-1, 2),
            np.asarray(membranes, int).reshape(-1, 2),
            np.array(roles, bool),
        )
    )


@pytest.mark.parametrize("count", [0, 1, 2, 4, 7])
@pytest.mark.parametrize("mode", ["none", "all", "even"])
def test_reference_graph_invariants_across_sizes(count, mode):
    t = chain(count)
    removed = [] if mode == "none" else list(t.cell_ids) if mode == "all" else list(t.cell_ids[::2])
    plan = cut.plan_cut(t, removed)
    expected = reference.remove(cut.topology_dict(t), removed)
    assert cut.topology_dict(plan.after) == expected["after"]
    assert list(plan.hurt_cell_ids) == expected["hurt_cell_ids"]
    assert list(plan.exposed_membrane_ids) == expected["exposed_membrane_ids"]
    for domain in cut.DOMAINS:
        kept, lost = plan.new_to_old[domain], plan.removed[domain]
        np.testing.assert_array_equal(
            np.sort(np.r_[kept, lost]), np.arange(len(getattr(t, domain + "_ids")))
        )
        np.testing.assert_array_equal(plan.old_to_new[domain][kept], np.arange(len(kept)))
    csr = cut.owner_csr(plan.after)
    assert csr["membrane_indptr"][-1] == len(plan.after.membrane_ids)
    assert csr["contact_indptr"][-1] == 2 * np.count_nonzero(plan.after.edge_is_contact)
