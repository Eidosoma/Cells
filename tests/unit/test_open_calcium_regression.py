"""Exact finite-exterior reduction and narrow closed-parser extraction retention."""

import ast
import copy
import hashlib
from pathlib import Path

import numpy as np
import pytest

from cells.core import surface_calcium_energy_spec as old_fuel
from cells.core import surface_calcium_spec as old_calcium
from cells.core.specs import ConfigError, SimulationSpec
from cells.numerics.fixed_step import rk4_step
from tests.unit.test_open_calcium import OWNERS, control, setup
from validation.tissue import open_calcium_fixtures as fixtures
from validation.tissue import open_calcium_reference as reference

PARENTS = {"calcium": old_calcium, "energy": old_fuel}


@pytest.mark.parametrize("family", fixtures.FAMILIES)
@pytest.mark.parametrize("padded", (False, True))
def test_empty_reservoir_world_reduces_exactly_to_ordinary_definition_and_full_RHS(family, padded):
    schema, model, _, raw, spec, state, p, context = setup(family, "empty", padded)
    parent_spec = PARENTS[family].parse(fixtures.original_definition(raw))
    original, layout = model.base.initial_values(parent_spec)
    for a, b in zip(state, original, strict=True):
        np.testing.assert_array_equal(a, b)
    for a, b in zip(model.parent_layout(p), layout, strict=True):
        np.testing.assert_array_equal(a, b)
    canonical = fixtures.original_definition(schema.to_dict(spec))
    assert canonical == PARENTS[family].to_dict(parent_spec)
    closed_context = (
        reference.finite.bind(canonical)
        if family == "energy"
        else reference.calcium.bind(canonical)
    )
    for time in (0.0, spec.experiment.end_time):
        u = control(schema, spec, time)
        expected = model.base.rhs(original, u, layout, layout.active, xp=np)
        actual = model.rhs(state, u, p, p.active, xp=np)
        for name in state._fields:
            np.testing.assert_array_equal(
                getattr(actual, name), getattr(expected, name), err_msg=name
            )
        vector = reference.flatten(context, state._asdict())
        independently_open = reference.evaluate(context, vector, time)[0]
        independently_closed = (
            reference.finite.evaluate(closed_context, vector, time)[0]
            if family == "energy"
            else reference.calcium.evaluate(closed_context, vector, time)[0]
        )
        np.testing.assert_array_equal(independently_open, independently_closed)
    model.check_values(state, spec)
    table = control_values_for(parent_spec)
    model.check_steps(spec, np.asarray([fixtures.DT]), table)
    model.base.check_steps(parent_spec, np.asarray([fixtures.DT]), table)
    # Evolve both actual owners separately. All original physical histories and
    # physical observations must still agree; new domain readouts are separate.
    old_rows, new_rows = [original], [state]
    u = control(schema, spec, 0.0)
    for _ in range(2):
        old_rows.append(
            rk4_step(
                lambda y, *args: model.base.rhs(y, *args, xp=np),
                old_rows[-1],
                fixtures.DT,
                u,
                layout,
                layout.active,
            )
        )
        new_rows.append(
            rk4_step(
                lambda y, *args: model.rhs(y, *args, xp=np),
                new_rows[-1],
                fixtures.DT,
                u,
                p,
                p.active,
            )
        )
        for name in state._fields:
            np.testing.assert_array_equal(
                getattr(new_rows[-1], name), getattr(old_rows[-1], name), err_msg=name
            )
    old_history = model.base.STATE_TYPE(
        *(np.stack(values) for values in zip(*old_rows, strict=True))
    )
    new_history = model.STATE_TYPE(*(np.stack(values) for values in zip(*new_rows, strict=True)))
    times = np.asarray([0.0, fixtures.DT, 2 * fixtures.DT])
    old_observed = model.base.observe_history(times, old_history, layout, times, parent_spec)
    new_observed = model.observe_history(times, new_history, p, times, spec)
    for name in model.base.OBSERVATION_FIELDS:
        np.testing.assert_array_equal(
            getattr(new_observed, name), getattr(old_observed, name), err_msg=name
        )
    assert set(vars(new_observed)) - set(vars(old_observed)) == {
        "ionic_moiety_fmol",
        "ionic_moiety_ceiling_fmol",
        "ideal_reservoir_active",
    }


def control_values_for(spec):
    from cells.core.schedule import control_values

    return control_values(spec, [0.0])


@pytest.mark.parametrize("family", fixtures.FAMILIES)
@pytest.mark.parametrize("case", ("all", "mixed"))
def test_ordinary_closed_ids_still_refuse_actual_reservoirs(family, case):
    raw = fixtures.original_definition(fixtures.definition(family, case))
    assert any(row["reservoir"] for row in raw["model"]["ionic"]["extracellular"])
    with pytest.raises(ConfigError, match="finite outside inventories"):
        PARENTS[family].parse(raw)


@pytest.mark.parametrize("family", fixtures.FAMILIES)
def test_private_decoders_preserve_actual_flags_and_do_not_admit_a_simulation(family):
    raw = fixtures.original_definition(fixtures.definition(family))
    declared = PARENTS[family]._decode_components(raw)
    assert type(declared) is old_calcium._OwnedDeclarations
    assert not isinstance(declared, SimulationSpec)
    assert not hasattr(declared, "to_dict")
    assert [row.reservoir for row in declared.model.extracellular] == [
        row["reservoir"] for row in raw["model"]["ionic"]["extracellular"]
    ]
    assert len({row.kinetic_law for row in declared.model.channels}) == 56
    if family == "energy":
        assert all(
            row.metabolism.kind == "finite_energy_pool@1"
            for row in (patch.pump for patch in declared.model.membranes)
            if row is not None
        )
        assert all(pool.initial_amount_fmol for pool in declared.model.energy_pools)


@pytest.mark.parametrize("family", fixtures.FAMILIES)
@pytest.mark.parametrize(
    "fault",
    (
        "missing",
        "unknown",
        "negative",
        "zero",
        "nan",
        "boolean",
        "no_open_limit",
        "initial_outside_limit",
        "closed_limit",
        "domain_policy",
        "exterior_policy",
    ),
)
def test_explicit_open_ceiling_admission_rejects_ambiguous_or_invalid_inputs(family, fault):
    raw = fixtures.definition(family, "empty" if fault == "closed_limit" else "all")
    m = raw["model"]
    if fault == "missing":
        m["ionic_moiety_ceiling_fmol"].pop("Ca")
    elif fault == "unknown":
        m["ionic_moiety_ceiling_fmol"]["invented"] = 1.0
    elif fault in ("negative", "zero", "nan", "boolean"):
        m["ionic_moiety_ceiling_fmol"]["Ca"] = {
            "negative": -1,
            "zero": 0,
            "nan": float("nan"),
            "boolean": True,
        }[fault]
    elif fault == "no_open_limit":
        m["ionic_moiety_ceiling_fmol"] = None
    elif fault == "initial_outside_limit":
        m["ionic_moiety_ceiling_fmol"]["Na"] *= 0.25
    elif fault == "closed_limit":
        m["ionic_moiety_ceiling_fmol"] = fixtures.ionic_totals(m)
    elif fault == "domain_policy":
        m["ionic_moiety_domain_policy"] = "conserved_initial_pools"
    else:
        m["exterior_policy"] = "implicit_replenishment"
    with pytest.raises(ConfigError):
        OWNERS[family][0].parse(raw)
    with pytest.raises(ValueError):
        reference.bind(raw)


@pytest.mark.parametrize("family", fixtures.FAMILIES)
@pytest.mark.parametrize("fault", ("cytosol_volume", "free_ion_amount", "free_ion_moiety"))
def test_open_decode_retains_existing_cross_owner_constraints(family, fault):
    raw = fixtures.definition(family)
    store = raw["model"]["stores"][0]["model"]
    cytosol = next(
        row for row in store["compartments"] if row["id"] == store["membrane"]["cytosol"]
    )
    if fault == "cytosol_volume":
        cytosol["volume_pL"] *= 1.01
    elif fault == "free_ion_amount":
        cytosol["initial_amount_fmol"]["Na"] += 0.1
    else:
        next(row for row in store["species"] if row["id"] == "Na")["moieties"]["Na"] = 2
    with pytest.raises(ConfigError):
        OWNERS[family][0].parse(raw)


@pytest.mark.parametrize(
    "path,expected",
    (
        (
            "src/cells/core/surface_calcium_spec.py",
            "55e7d3dd78fd8dad1e56e562feacef3aa02af7e5dfacbb093f6581b48ecf302d",
        ),
        (
            "src/cells/core/surface_calcium_energy_spec.py",
            "ab7840fce6131206ab3ea5a0d16914a7ecb5d5ae1cd243a80b75be59893b4aaf",
        ),
    ),
)
def test_mechanically_reversing_private_extraction_retains_the_complete_closed_parser_AST(
    path, expected
):
    root = Path(__file__).resolve().parents[2]
    tree = ast.parse((root / path).read_text())
    functions = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
    decoder = copy.deepcopy(functions["_decode_components"])
    decoder.name = "parse"
    decoder.args = ast.parse("def parse(data): pass").body[0].args
    assert isinstance(decoder.body[0], ast.Expr) and isinstance(decoder.body[0].value, ast.Constant)
    decoder.body.pop(0)
    if path.endswith("/surface_calcium_spec.py"):
        decoder.body = [
            copy.deepcopy(functions["_require_finite_exterior"].body[0])
            if isinstance(node, ast.If) and ast.unparse(node.test) == "exterior_check is not None"
            else node
            for node in decoder.body
        ]
        returned = decoder.body.pop()
        assert isinstance(returned, ast.Return)
        returned.value.func = ast.Name(id="SimulationSpec", ctx=ast.Load())
        decoder.body.append(
            ast.Assign(targets=[ast.Name(id="spec", ctx=ast.Store())], value=returned.value)
        )
        assert "exterior_check=_require_finite_exterior" in ast.unparse(functions["parse"])
    else:
        for node in ast.walk(decoder):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "calcium_decoder"
            ):
                node.func = ast.Attribute(
                    value=ast.Name(id="prior", ctx=ast.Load()), attr="parse", ctx=ast.Load()
                )
        decoder.body.pop()
        assert "calcium_decoder=prior.parse" in ast.unparse(functions["parse"])
    decoder.body += copy.deepcopy(functions["parse"].body[2:])
    assert (
        hashlib.sha256(ast.dump(decoder, include_attributes=False).encode()).hexdigest() == expected
    )


def test_independent_open_reference_closure_contains_full_56law_ER_and_fuel_equations():
    import os

    root = Path(os.environ.get("CELLS_COMPONENT_SOURCE_ROOT", Path(__file__).resolve().parents[2]))
    manifest = reference.dependency_manifest(root)
    assert {
        "validation/tissue/open_calcium_reference.py",
        "validation/tissue/surface_calcium_reference.py",
        "validation/tissue/surface_calcium_energy_reference.py",
        "validation/tissue/surface_kinetic_reference.py",
        "validation/chemistry/finite_energy_reference.py",
        "tests/reference_er_calcium.py",
    } <= set(manifest)
    assert "tests/__init__.py" in manifest


@pytest.mark.parametrize("location", ("initializer", "legacy", "reference"))
def test_reference_import_audit_rejects_production_imports_after_package_admission(
    tmp_path, monkeypatch, location
):
    validation = tmp_path / "validation"
    legacy = tmp_path / "tests"
    validation.mkdir()
    legacy.mkdir()
    own = validation / "independent.py"
    own.write_text("from tests import reference_scalar\n")
    initializer = legacy / "__init__.py"
    initializer.write_text('"""Independent scalar helpers."""\n')
    scalar = legacy / "reference_scalar.py"
    scalar.write_text("def value():\n    return 1\n")
    monkeypatch.setattr(reference, "__file__", str(own))
    manifest = reference.dependency_manifest(tmp_path)
    assert set(manifest) == {
        "validation/independent.py",
        "tests/__init__.py",
        "tests/reference_scalar.py",
    }
    if location == "initializer":
        initializer.write_text("import cells\n")
    elif location == "legacy":
        scalar.write_text("def value():\n    from cells import models\n    return models\n")
    else:
        own.write_text("import jax\n")
    with pytest.raises(ValueError, match="initializer|Production/JAX"):
        reference.dependency_manifest(tmp_path)
