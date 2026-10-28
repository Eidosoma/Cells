"""Stable identities, explicit removed material, native source limits and CPU gathers."""

import hashlib
import json
import os
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from cells.processes import betse_tissue_cut as cut
from validation.topology import betse_tissue_cut_reference as reference
from validation.topology.betse_tissue_cut_fixtures import cases

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


@pytest.mark.parametrize("name", [r["name"] for r in cases()])
def test_actual_native_survivor_identities_contact_and_field_maps(name):
    raw = native(name)
    t = cut.topology_from_dict(raw["before"]["topology"])
    plan = cut.plan_cut(t, raw["input"]["remove_cell_ids"])
    assert (
        cut.LAW_ID == PROTOCOL["law_id"]
        and cut.topology_dict(plan.after) == raw["after"]["topology"]
    )
    np.testing.assert_array_equal(
        np.array(raw["before"]["sim"]["cc_cells"])[:, plan.new_to_old["cell"]],
        raw["after"]["sim"]["cc_cells"],
    )
    np.testing.assert_array_equal(
        np.array(raw["before"]["sim"]["mem_gate"])[plan.new_to_old["membrane"]],
        raw["after"]["sim"]["mem_gate"],
    )
    hurt = [
        cell
        for cell, flag in zip(plan.after.cell_ids, raw["after"]["sim"]["hurt_mask"], strict=True)
        if flag
    ]
    assert list(plan.hurt_cell_ids) == hurt
    csr = cut.owner_csr(plan.after)
    matrix = np.zeros((len(plan.after.cell_ids), len(plan.after.membrane_ids)))
    for i in range(len(plan.after.cell_ids)):
        matrix[
            i, csr["membrane_indices"][csr["membrane_indptr"][i] : csr["membrane_indptr"][i + 1]]
        ] = 1
    np.testing.assert_array_equal(matrix, raw["after"]["cells"]["M_sum_mems"])
    environmental = np.zeros((len(plan.after.environment_ids), len(plan.after.membrane_ids)))
    environmental[plan.after.membrane_environment, np.arange(len(plan.after.membrane_ids))] = raw[
        "after"
    ]["cells"]["mem_sa"]
    np.testing.assert_array_equal(environmental, raw["after"]["cells"]["M_divmap_mem2ecm"])
    assert "DECMesh.cut_mesh" in raw["call_trace"] and "Cells.graphLaplacian" in raw["call_trace"]
    assert "Simulator.initDenv" in raw["call_trace"]
    evidence(
        name,
        dict(
            before_identity=plan.before_identity,
            after_identity=plan.after_identity,
            after=cut.topology_dict(plan.after),
            removed={d: v.tolist() for d, v in plan.removed.items()},
            hurt_cell_ids=plan.hurt_cell_ids,
            exposed_membrane_ids=plan.exposed_membrane_ids,
            native_call_trace=raw["call_trace"],
        ),
    )


@pytest.mark.parametrize("removed", [[], ["A"], ["B"], ["C"], ["A", "B"], ["A", "B", "C"]])
def test_independent_decimal_material_partition_and_empty_domains(removed):
    t, raw = sample()
    owned = fields(raw)
    result = cut.apply_cut(t, removed, owned)
    expected = reference.remove(raw["before"]["topology"], removed)
    assert cut.topology_dict(result.plan.after) == expected["after"]
    for domain in cut.DOMAINS:
        np.testing.assert_array_equal(
            result.plan.new_to_old[domain], expected["new_to_old"][domain]
        )
        np.testing.assert_array_equal(
            result.plan.old_to_new[domain], expected["old_to_new"][domain]
        )
    for name, field in owned.items():
        check_field(
            field, result.fields[name], reference.field_cut(reference_field(field), expected)
        )
    assert result.plan.after.environment_ids == t.environment_ids
    if removed:
        assert result.plan.invalidated and result.plan.before_identity != result.plan.after_identity
    else:
        assert (
            not result.plan.invalidated
            and result.plan.before_identity == result.plan.after_identity
        )
        for name, field in owned.items():
            np.testing.assert_array_equal(result.fields[name].retained, field.values)
    evidence(
        "partition-" + ("-".join(removed) or "none"),
        dict(
            removed=removed,
            identities=[result.plan.before_identity, result.plan.after_identity],
            ledger={
                name: {
                    key: None if value is None else np.asarray(value).tolist()
                    for key, value in f._asdict().items()
                }
                for name, f in result.fields.items()
            },
            removed_owner_ids=result.removed_owner_ids,
        ),
    )


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


def test_field_hanging_edge_is_not_a_contact_wound_and_orientation_survives():
    t, raw = sample()
    left = cut.plan_cut(t, ["A"])
    middle = cut.plan_cut(t, ["B"])
    assert left.hurt_cell_ids == ("B",) and "C" not in left.hurt_cell_ids
    assert middle.after.edge_ids == ("field:C>A",)
    np.testing.assert_array_equal(middle.after.edge_cells, [[1, 0]])
    assert middle.exposed_membrane_ids == ("A:m2", "C:m0")
    assert raw["targets_dec_edges"] == [0, 1]
    assert list(middle.new_to_old["edge"]) != raw["targets_dec_edges"]


def test_environment_measure_change_preserves_amount_without_implicit_release():
    t, raw = sample()
    owned = fields(raw)
    before = owned["environment"]
    new_volume = np.array(raw["after"]["cells"]["true_ecm_vol"]) * 1e15
    owned["environment"] = replace(before, replacement_measure=new_volume)
    result = cut.apply_cut(t, ["B"], owned)
    oracle = reference.remove(cut.topology_dict(t), ["B"])
    check_field(
        owned["environment"],
        result.fields["environment"],
        reference.field_cut(reference_field(owned["environment"]), oracle),
    )
    np.testing.assert_allclose(
        result.fields["environment"].retained * new_volume,
        before.values * before.measure,
        rtol=5e-12,
        atol=2e-12,
    )
    assert result.removed_owner_ids["environment"] == ()
    native_before = np.sum(before.values * before.measure, axis=-1)
    native_after = np.sum(np.array(raw["after"]["sim"]["cc_env"]) * new_volume, axis=-1)
    assert np.max(np.abs(native_after - native_before)) > 1e-6
    np.testing.assert_array_equal(result.fields["environment"].removed_total, 0)
    evidence(
        "environment-volume",
        dict(
            native_material_change_fmol=(native_after - native_before).tolist(),
            conservative_residual_fmol=result.fields["environment"].balance_residual.tolist(),
            release_to_environment=False,
        ),
    )


def test_explicit_axes_do_not_infer_native_length_or_list_ownership():
    t, _ = sample()
    plan = cut.plan_cut(t, ["B"])
    matrix = np.arange(9.0, dtype=float).reshape(3, 3)
    np.testing.assert_array_equal(
        cut.remap_axes(matrix, plan, [(0, "cell"), (1, "cell")]), matrix[[0, 2]][:, [0, 2]]
    )
    result = cut.apply_cut(
        t,
        ["B"],
        {
            "global": cut.OwnedField(np.array([111.0, 222.0, 333.0]), "global", axis=None),
            "nested": cut.OwnedField(np.arange(6.0).reshape(2, 3), "cell", axis=1),
            "list": cut.OwnedField(np.array([10.0, 20.0, 30.0]), "cell"),
        },
    )
    np.testing.assert_array_equal(result.fields["global"].retained, [111.0, 222.0, 333.0])
    np.testing.assert_array_equal(result.fields["nested"].retained, [[0.0, 2.0], [3.0, 5.0]])
    np.testing.assert_array_equal(result.fields["list"].retained, [10.0, 30.0])
    assert native("equal-length-global")["after"]["sim"]["equal_length_global"] == [111.0, 333.0]
    assert native("list-middle-tail")["after"]["sim"]["witness_list"] == [30.0]


def test_native_authentication_resets_and_preserved_limits():
    manifest = native("source-manifest")
    assert (
        manifest["status"] == "passed"
        and manifest["no_production_or_jax_imports"]
        and not manifest["native_simulation"]
    )
    assert manifest["successful_cases"] == 3 and manifest["observed_native_limits"] == 7
    assert manifest["revision"] == PROTOCOL["native_source"]["revision"]
    root = Path(os.environ["CELLS_BETSE_CUT_NATIVE_CAPTURE"])
    for relative, expected in PROTOCOL["native_source"]["source_sha256"].items():
        assert hashlib.sha256((root / "upstream" / relative).read_bytes()).hexdigest() == expected
    for name in manifest["limits"]:
        assert native(name)["status"] == "observed_native_limit"
    raw = native()
    assert np.all(np.array(raw["before"]["sim"]["conc_J_x"]) == 7)
    assert np.all(np.array(raw["after"]["sim"]["conc_J_x"]) == 0)
    assert np.any(
        np.array(raw["before"]["sim"]["D_env_weight"])
        != np.array(raw["after"]["sim"]["D_env_weight"])
    )


@pytest.mark.parametrize(
    "fault",
    [
        "ids",
        "cell_owner",
        "environment",
        "endpoints",
        "self_edge",
        "contact_owner",
        "contact_reuse",
        "field_face",
        "integer_roles",
        "missing_owner",
        "missing_key",
    ],
)
def test_invalid_topology_rejects(fault):
    t, _ = sample()
    data = cut.topology_dict(t)
    if fault == "ids":
        data["cell_ids"][1] = "A"
    elif fault == "cell_owner":
        data["membrane_cell"][0] = 3
    elif fault == "environment":
        data["membrane_environment"][0] = 10000
    elif fault == "endpoints":
        data["edge_cells"][0][0] = -1
    elif fault == "self_edge":
        data["edge_cells"][0] = [0, 0]
    elif fault == "contact_owner":
        data["edge_membranes"][0][0] = 4
    elif fault == "contact_reuse":
        data["edge_membranes"][1][0] = data["edge_membranes"][0][0]
    elif fault == "field_face":
        data["edge_membranes"][-1] = [0, 1]
    elif fault == "integer_roles":
        data["edge_is_contact"] = [int(v) for v in data["edge_is_contact"]]
    elif fault == "missing_owner":
        data["membrane_cell"] = []
    else:
        data.pop("membrane_cell")
    with pytest.raises(ValueError):
        cut.topology_from_dict(data)


@pytest.mark.parametrize(
    "fault",
    [
        "domain",
        "axis",
        "bool_axis",
        "derived",
        "nonfinite",
        "negative",
        "units",
        "missing_measure",
        "zero_measure",
        "negative_scale",
        "bool_scale",
        "string_scale",
        "overflow_quantity",
        "overflow_density",
        "bad_global",
    ],
)
def test_invalid_fields_reject_atomically(fault):
    t, raw = sample()
    owned = fields(raw)
    f = owned["ions"]
    if fault == "domain":
        f = replace(f, domain="unknown")
    elif fault == "axis":
        f = replace(f, axis=0)
    elif fault == "bool_axis":
        f = replace(f, axis=True)
    elif fault == "derived":
        f = replace(f, kind="derived")
    elif fault in ("nonfinite", "negative"):
        value = np.array(f.values, copy=True)
        value[0, 0] = np.nan if fault == "nonfinite" else -1
        f = replace(f, values=value)
    elif fault == "units":
        f = replace(f, units="")
    elif fault == "missing_measure":
        f = replace(f, measure=None)
    elif fault == "zero_measure":
        f = replace(f, measure=np.zeros(3))
    elif fault in ("negative_scale", "bool_scale", "string_scale"):
        f = replace(
            f, amount_scale={"negative_scale": -1, "bool_scale": True, "string_scale": "1"}[fault]
        )
    elif fault == "overflow_quantity":
        f = replace(f, values=np.ones((2, 3)) * 1e308, measure=np.ones(3) * 1e308)
    elif fault == "overflow_density":
        f = replace(f, replacement_measure=np.ones(2) * 1e-310)
    else:
        f = replace(f, domain="global", axis=0)
    before = np.array(f.values, copy=True)
    owned["invalid"] = f
    with pytest.raises(ValueError):
        cut.apply_cut(t, ["B"], owned)
    np.testing.assert_array_equal(f.values, before)


def test_noop_and_empty_do_not_hide_invalid_measure_or_selection():
    t, raw = sample()
    for removed in (["missing"], ["A", "A"]):
        with pytest.raises(ValueError):
            cut.plan_cut(t, removed)
    f = fields(raw)["ions"]
    with pytest.raises(ValueError):
        cut.apply_cut(t, [], {"ions": replace(f, replacement_measure=np.ones(3))})
    empty = chain(0)
    bad = cut.OwnedField(
        np.empty((2, 0)), "cell", kind="density", units="mM", quantity_units="fmol", measure=np.nan
    )
    with pytest.raises(ValueError):
        cut.apply_cut(empty, [], {"ions": bad})


def test_sequential_cut_checkpoint_owner_contract_and_layout_mismatch(tmp_path):
    t, raw = sample()
    owned = fields(raw)
    first = cut.apply_cut(t, ["B"], owned)
    manifest = cut.checkpoint_manifest(first.plan.after, first.field_metadata)
    path = tmp_path / "cut-layout.json"
    path.write_text(json.dumps(manifest))
    loaded = json.loads(path.read_text())
    restored = cut.topology_from_dict(loaded["topology"])
    assert (
        cut.validate_checkpoint_manifest(loaded, restored, first.field_metadata)
        == first.field_metadata
    )
    with pytest.raises(ValueError):
        cut.validate_checkpoint_manifest(loaded, t)
    changed = deepcopy(loaded)
    changed["fields"]["ions"]["units"] = "wrong"
    with pytest.raises(ValueError):
        cut.validate_checkpoint_manifest(changed, restored)
    changed = deepcopy(loaded)
    changed["topology"]["cell_ids"] = ["X", "C"]
    with pytest.raises(ValueError):
        cut.validate_checkpoint_manifest(changed, restored)
    restarted = {}
    for name, field in owned.items():
        output = first.fields[name]
        restarted[name] = replace(
            field,
            values=output.retained,
            axis=first.field_metadata[name]["axis"],
            measure=output.retained_measure if field.kind == "density" else None,
        )
    second = cut.apply_cut(restored, ["A"], restarted)
    direct = cut.apply_cut(t, ["A", "B"], owned)
    assert cut.topology_dict(second.plan.after) == cut.topology_dict(direct.plan.after)
    for name in owned:
        np.testing.assert_array_equal(second.fields[name].retained, direct.fields[name].retained)
        if direct.fields[name].removed_total is not None:
            np.testing.assert_allclose(
                first.fields[name].removed_total + second.fields[name].removed_total,
                direct.fields[name].removed_total,
                rtol=5e-12,
                atol=3e-22 if owned[name].units == "C" else 2e-12,
            )
    evidence(
        "checkpoint",
        dict(
            manifest=loaded,
            sequential_after_identity=second.plan.after_identity,
            direct_after_identity=direct.plan.after_identity,
            removed_contents_persist=True,
        ),
    )


def test_input_and_plan_immutability():
    t, raw = sample()
    owned = fields(raw)
    original = owned["ions"].values.copy()
    result = cut.apply_cut(t, ["B"], owned)
    result.fields["ions"].retained[0, 0] = 99
    np.testing.assert_array_equal(owned["ions"].values, original)
    with pytest.raises(ValueError):
        result.plan.new_to_old["cell"][0] = 99
    with pytest.raises(TypeError):
        result.plan.new_to_old["cell"] = np.array([99])


def test_jax_static_gathers_and_extensive_removed_ledger():
    import jax
    import jax.numpy as jnp

    t, raw = sample()
    plan = cut.plan_cut(t, ["B"])
    field = cut.validate_field(fields(raw)["ions"], plan)
    fn = jax.jit(lambda values: cut.remap_field(replace(field, values=values), plan, xp=jnp))
    actual, expected = fn(field.values), cut.remap_field(field, plan)
    for a, b in zip(actual, expected, strict=True):
        if a is not None:
            np.testing.assert_allclose(a, b, rtol=5e-12, atol=2e-12)
    matrix = np.arange(9.0).reshape(3, 3)
    gather = jax.jit(lambda x: cut.remap_axes(x, plan, [(0, "cell"), (1, "cell")], xp=jnp))
    np.testing.assert_array_equal(gather(matrix), matrix[[0, 2]][:, [0, 2]])
    assert all(device.platform == "cpu" for device in jax.devices())
    evidence(
        "jax-gather",
        dict(
            retained=np.asarray(actual.retained).tolist(),
            removed=np.asarray(actual.removed_quantity).tolist(),
            backend_devices=[d.platform for d in jax.devices()],
        ),
    )


def test_jax_density_new_measure_and_independent_batches():
    import jax
    import jax.numpy as jnp

    t, raw = sample()
    plan = cut.plan_cut(t, ["B"])
    original = fields(raw)["ions"]
    field = cut.validate_field(replace(original, replacement_measure=np.array([1.1, 2.2])), plan)
    fn = jax.jit(
        jax.vmap(lambda values: cut.remap_field(replace(field, values=values), plan, xp=jnp))
    )
    batch = np.stack([field.values, field.values * 2, field.values * 0.5])
    actual = fn(batch)
    for i in range(3):
        expected = cut.remap_field(replace(field, values=batch[i]), plan)
        for a, b in zip(actual, expected, strict=True):
            if a is not None:
                np.testing.assert_allclose(a[i], b, rtol=5e-12, atol=2e-12)
    evidence(
        "jax-density",
        dict(
            retained=np.asarray(actual.retained).tolist(),
            residual=np.asarray(actual.balance_residual).tolist(),
        ),
    )


def test_jax_complete_removal_and_global_identity():
    import jax
    import jax.numpy as jnp

    t, raw = sample()
    plan = cut.plan_cut(t, list(t.cell_ids))
    field = cut.validate_field(fields(raw)["ions"], plan)
    result = jax.jit(lambda x: cut.remap_field(replace(field, values=x), plan, xp=jnp))(
        field.values
    )
    assert result.retained.shape == (2, 0)
    np.testing.assert_allclose(result.previous_total, result.removed_total, rtol=5e-12, atol=2e-12)
    global_field = cut.validate_field(fields(raw)["global_equal_cell_count"], plan)
    keep = jax.jit(
        lambda x: cut.remap_field(replace(global_field, values=x), plan, xp=jnp).retained
    )
    np.testing.assert_array_equal(keep(global_field.values), global_field.values)
    evidence(
        "jax-empty",
        dict(
            empty_shape=list(result.retained.shape),
            removed_total=np.asarray(result.removed_total).tolist(),
        ),
    )
