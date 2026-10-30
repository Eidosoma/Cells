"""Associated declared budgets, exact five-term sums and original energy gates."""

import ast
import math
from dataclasses import replace
from functools import lru_cache
from pathlib import Path
from types import SimpleNamespace

import jax
import jax.numpy as jnp
import numpy as np
import pytest

from cells.core import physiology_protein_interval_accounting as accounting
from cells.core import physiology_tissue_binding as units
from cells.core.specs import parse_spec
from cells.core.state import Checkpoint
from cells.models import physiology_permeability_view as view
from cells.numerics import physiology_protein_drive_arrays as arrays
from tests.integration.test_physiology_protein_charge_view import changed_protein
from tests.integration.test_physiology_protein_work_view import reservoir_transfer
from tests.unit.test_physiology_protein_electrical_arrays import prepare, two_clamps
from tests.unit.test_physiology_protein_interval_accounting import evidence
from tests.unit.test_physiology_protein_work_arrays import frame, geometry, inputs, record
from tests.unit.test_physiology_tissue_binding import arguments, component_state
from tests.unit.test_physiology_tissue_step import KINDS, case, tissue
from validation.tissue import physiology_protein_chemical_arrays_reference as chemical_reference
from validation.tissue import physiology_protein_drive_arrays_reference as reference

PROVENANCE = "Synthetic declared work/free-energy dissipation; no inferred physical law"
IMPLEMENTATIONS = dict(passive=view.passive, ionic=view.ionic, calcium=view.calcium, fuel=view.fuel)


@lru_cache(maxsize=1)
def host_expression():
    path = Path(__file__).resolve().parents[2] / "src/cells/core/physiology_protein_transition.py"
    tree = ast.parse(path.read_text())
    accept = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "accept")
    expression = next(
        n.value
        for n in ast.walk(accept)
        if isinstance(n, ast.Assign)
        and isinstance(n.value, ast.Call)
        and isinstance(n.value.func, ast.Attribute)
        and isinstance(n.value.func.value, ast.Name)
        and n.value.func.value.id == "math"
        and n.value.func.attr == "fsum"
    )
    return compile(ast.Expression(expression), str(path), "eval")


def host_residual(g, u, clamp, external, dissipated):
    proposal = SimpleNamespace(
        thermodynamics=SimpleNamespace(total_free_energy_change_pJ=float(g)),
        electrical=SimpleNamespace(capacitor_energy_change_pJ=float(u), clamp_work_pJ=float(clamp)),
    )
    budget = SimpleNamespace(
        external_work_pJ=float(external), dissipated_free_energy_pJ=float(dissipated)
    )
    return eval(host_expression(), {"math": math}, dict(proposal=proposal, budget=budget))


def ulp_error(actual, expected):
    return abs(float(actual) - float(expected)) / (4 * abs(float(np.spacing(expected))))


def report(result):
    return result._asdict() | dict(
        conditional_work=record(result.conditional_work),
        energy_balance=result.energy_balance._asdict(),
    )


@lru_cache(maxsize=8)
def source(kind="passive", at_event=False):
    return case(kind, at_event=at_event, source_dt_scale=0.5)


def prepared(spec, point, binding, anchor, before, after, *, valence=-1.0, standard=1.0):
    b, e, _, _, implementation = prepare(
        spec, point, binding, anchor, before, after, valence=valence
    )
    data = (anchor.protein, before.protein, after.protein, b, e, geometry(binding))
    parameters = frame(spec, valence=valence, standard=standard) | dict(
        implementation=implementation
    )
    return data, parameters


def compare(
    name,
    spec,
    point,
    binding,
    anchor,
    before,
    after,
    *,
    valence=-1.0,
    standard=1.0,
    external=None,
    dissipated=2.0**-18,
    expected_valid=True,
):
    data, parameters = prepared(
        spec, point, binding, anchor, before, after, valence=valence, standard=standard
    )
    original = jax.tree.map(lambda a: a.tobytes(), data)
    conditional = arrays.endpoint_work.evaluate(*data, **parameters, xp=np)
    if external is None:
        external = math.fsum((conditional.conditional_reversible_work_pJ, dissipated))
    actual = arrays.evaluate(
        *data,
        **parameters,
        external_work_pJ=external,
        dissipated_free_energy_pJ=dissipated,
        budget_provenance=PROVENANCE,
        xp=np,
    )
    declaration = inputs(
        spec, point, binding, anchor, before, after, frame(spec, valence=valence, standard=standard)
    ) | dict(
        external_work_pJ=external,
        dissipated_free_energy_pJ=dissipated,
        budget_provenance=PROVENANCE,
    )
    expected = reference.evaluate(**declaration)
    energy = actual.energy_balance
    host = host_residual(
        actual.conditional_work.chemical.total_free_energy_change_pJ,
        actual.conditional_work.electrical.capacitor_energy_change_pJ,
        actual.conditional_work.electrical.clamp_work_pJ,
        external,
        dissipated,
    )
    host_limit = accounting._limits(spec, point.state, data[3].runtime_layout)["energy"]
    assert (
        energy.physical_energy_tolerance_pJ
        == host_limit
        == expected["energy_balance"]["physical_energy_tolerance_pJ"]
    )
    errors = dict(
        host_five_term_arithmetic=ulp_error(energy.balance_residual_pJ, host),
        independent_SI=abs(energy.balance_residual_pJ - expected["direct_SI_residual_pJ"])
        / (3e-14 + 3e-10 * abs(expected["direct_SI_residual_pJ"])),
    )
    if (
        expected["conditional_work"]["capacitor_energy_change_pJ"]
        == expected["conditional_work"]["clamp_work_pJ"]
        == 0
        and external == dissipated
    ):
        _, ratio = chemical_reference.precision(
            energy.balance_residual_pJ, expected["direct_SI_residual_pJ"]
        )
        errors["tiny_residual_relative"] = float(ratio)
    evidence(
        "protein-drive-arrays-" + name,
        dict(
            inputs=declaration,
            actual=report(actual),
            expected=expected,
            errors=errors,
            maximum_error_fraction=max(errors.values()),
            expected_valid=expected_valid,
            host_residual_pJ=host,
            host_energy_limit_pJ=host_limit,
            host_arithmetic_only=True,
            no_loop_acceptance=True,
        ),
    )
    assert max(errors.values()) <= 1
    assert bool(actual.valid) == expected_valid, actual.checks
    assert not actual.valid or expected["valid"]
    assert bool(energy.checks["original_physical_energy_budget"]) == (abs(host) <= host_limit)
    assert original == jax.tree.map(lambda a: a.tobytes(), data)
    return actual


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("at_event", (False, True))
def test_full_associated_initial_evolved_work_obeys_host_and_independent_SI_budget(kind, at_event):
    spec, point, binding, anchor, _ = source(kind, at_event)
    before, after = (
        changed_protein(binding, anchor),
        changed_protein(binding, changed_protein(binding, anchor)),
    )
    for stage in range(2):
        compare(
            kind + "-" + str(at_event) + "-" + str(stage),
            spec,
            point,
            binding,
            anchor,
            before,
            after,
        )
        if stage == 0:
            for _ in range(2 if at_event else 1):
                point = tissue.advance(spec, point, binding, anchor).checkpoint


@pytest.mark.parametrize("shared", (False, True))
def test_unequal_reservoir_ports_and_common_shift_use_the_actual_work_contract(shared):
    for shift in (0.0, 0.017):
        spec, point, binding, anchor = two_clamps(shared, shift)
        after = reservoir_transfer(spec, binding, anchor)
        actual = compare(
            "clamp-" + str(shared) + "-" + str(shift),
            spec,
            point,
            binding,
            anchor,
            anchor,
            after,
            dissipated=0.0,
        )
        assert (
            actual.energy_balance.external_work_pJ
            == actual.conditional_work.conditional_reversible_work_pJ
        )


def test_signed_external_work_reversal_and_zero_effect_are_admitted():
    spec, point, binding, anchor = two_clamps(True)
    after = reservoir_transfer(spec, binding, anchor)
    forward = compare("forward", spec, point, binding, anchor, anchor, after, dissipated=0.0)
    backward = compare("backward", spec, point, binding, anchor, after, anchor, dissipated=0.0)
    zero = compare("zero", spec, point, binding, anchor, anchor, anchor, dissipated=0.0)
    assert forward.energy_balance.external_work_pJ * backward.energy_balance.external_work_pJ < 0
    assert zero.energy_balance.balance_residual_pJ == 0


def tiny_case():
    spec, point, binding, anchor = two_clamps(True)
    stock = 2.0**-40
    anchor = replace(
        anchor,
        protein=anchor.protein._replace(
            cell_mol_m3=np.full_like(anchor.protein.cell_mol_m3, stock),
            environment_mol_m3=np.full_like(anchor.protein.environment_mol_m3, stock),
        ),
    )
    indices = [
        binding.component.environment_ids.index(row.id)
        for row in spec.model.extracellular
        if row.reservoir
    ]
    values = np.array(anchor.protein.environment_mol_m3)
    values[indices[0]] -= 2.0**-90
    values[indices[1]] += 2.0**-90
    after = replace(anchor, protein=anchor.protein._replace(environment_mol_m3=values))
    return spec, point, binding, anchor, after


@pytest.mark.parametrize("declaration", (2.0**900, np.finfo(np.float64).max))
def test_tiny_neutral_residual_survives_huge_equal_declarations(declaration):
    spec, point, binding, anchor, after = tiny_case()
    actual = compare(
        "tiny-" + float(declaration).hex(),
        spec,
        point,
        binding,
        anchor,
        anchor,
        after,
        valence=0.0,
        standard=2.0**-40,
        external=declaration,
        dissipated=declaration,
    )
    assert (
        actual.energy_balance.balance_residual_pJ
        == actual.conditional_work.conditional_reversible_work_pJ
        > 0
    )
    assert actual.numerical_bound_pJ > actual.energy_balance.physical_energy_tolerance_pJ


def test_huge_roundoff_bound_does_not_hide_a_missing_external_work_term():
    spec, point, binding, anchor, _ = source()
    after = changed_protein(binding, anchor)
    actual = compare(
        "missing-work",
        spec,
        point,
        binding,
        anchor,
        anchor,
        after,
        external=2.0**900,
        dissipated=2.0**900,
        expected_valid=False,
    )
    assert actual.conditional_work.valid
    energy = actual.energy_balance
    assert abs(energy.balance_residual_pJ) > energy.physical_energy_tolerance_pJ
    assert actual.numerical_bound_pJ > abs(energy.balance_residual_pJ)
    naive = 0.0
    for value in energy.raw_terms_pJ:
        naive += float(value)
    assert naive == 0 and energy.balance_residual_pJ != 0


@pytest.mark.parametrize("profile", ("lost", "cancellation"))
def test_balanced_declaration_cannot_override_an_unresolved_associated_work(profile):
    if profile == "lost":
        spec, point, binding, anchor, after = tiny_case()
        valence, standard = -1.0, 2.0**-40
    else:
        spec, point, binding, anchor = two_clamps(True)
        after = reservoir_transfer(spec, binding, anchor)
        data, params = prepared(spec, point, binding, anchor, anchor, after)
        initial = arrays.endpoint_work.evaluate(*data, **params, xp=np)
        valence = -initial.chemical.total_free_energy_change_pJ / initial.electrical.clamp_work_pJ
        standard = 1.0
    actual = compare(
        "unresolved-" + profile,
        spec,
        point,
        binding,
        anchor,
        anchor,
        after,
        valence=valence,
        standard=standard,
        dissipated=0.0,
        expected_valid=False,
    )
    assert not actual.conditional_work.valid and actual.energy_balance.valid
    assert not actual.checks["associated_conditional_work"]


@pytest.mark.parametrize(
    "edit", ("after_protein", "reference", "geometry", "permeability", "control")
)
def test_full_wrapper_recomputes_work_and_rejects_stale_complete_inputs(edit):
    spec, point, binding, anchor, _ = source()
    after = changed_protein(binding, anchor)
    data, params = prepared(spec, point, binding, anchor, anchor, after)
    data = list(data)
    work = arrays.endpoint_work.evaluate(*data, **params, xp=np)
    if edit in ("after_protein", "reference"):
        data[2 if edit == "after_protein" else 0] = changed_protein(
            binding, after if edit == "after_protein" else anchor
        ).protein
    elif edit == "geometry":
        data[5] = data[5]._replace(cell_volume_m3=data[5].cell_volume_m3 * 1e15)
    elif edit == "permeability":
        data[4] = data[4]._replace(
            runtime_layout=data[4].runtime_layout._replace(
                membrane_permeability=data[4].runtime_layout.membrane_permeability * 0.9
            )
        )
    else:
        data[4] = data[4]._replace(
            source_control=type(data[4].source_control)(*(v * 0.9 for v in data[4].source_control))
        )
    actual = arrays.evaluate(
        *data,
        **params,
        external_work_pJ=work.conditional_reversible_work_pJ,
        dissipated_free_energy_pJ=0.0,
        budget_provenance=PROVENANCE,
        xp=np,
    )
    assert not actual.valid and not actual.checks["associated_conditional_work"]


@pytest.mark.parametrize(
    "edit",
    (
        "W_nan",
        "W_inf",
        "D_nan",
        "D_inf",
        "negative_D",
        "dtype",
        "shape",
        "bool",
        "provenance",
        "overflow",
    ),
)
def test_declared_domain_precision_and_static_provenance_are_explicit(edit):
    spec, point, binding, anchor, _ = source()
    data, params = prepared(spec, point, binding, anchor, anchor, changed_protein(binding, anchor))
    budget = dict(external_work_pJ=0.0, dissipated_free_energy_pJ=0.0, budget_provenance=PROVENANCE)
    if edit in ("dtype", "shape", "bool", "provenance"):
        if edit == "provenance":
            budget["budget_provenance"] = "  "
        else:
            budget["external_work_pJ"] = dict(
                dtype=np.float32(0), shape=np.array([0.0]), bool=True
            )[edit]
        with pytest.raises(ValueError, match="provenance" if edit == "provenance" else "float64"):
            arrays.evaluate(*data, **params, **budget, xp=np)
        return
    if edit == "negative_D":
        budget["dissipated_free_energy_pJ"] = -1e-5
    elif edit == "overflow":
        budget.update(
            external_work_pJ=-np.finfo(np.float64).max,
            dissipated_free_energy_pJ=np.finfo(np.float64).max,
        )
    else:
        budget["external_work_pJ" if edit.startswith("W") else "dissipated_free_energy_pJ"] = (
            np.nan if edit.endswith("nan") else np.inf
        )
    with np.errstate(all="ignore"):
        actual = arrays.evaluate(*data, **params, **budget, xp=np)
    assert not actual.valid
    e = actual.energy_balance
    if edit == "negative_D":
        assert not e.checks["nonnegative_declared_dissipation"]
    elif edit == "overflow":
        assert e.checks["finite_energy_inputs"] and not e.checks["finite_arithmetic"]
    else:
        assert not e.checks["finite_energy_inputs"]
    evidence(
        "protein-drive-domain-" + edit,
        dict(
            valid=actual.valid,
            budget_checks=e.checks,
            raw_term_bits=np.asarray(e.raw_terms_pJ).view(np.uint64),
            residual_expansion_bits=np.asarray(e.residual_expansion_pJ).view(np.uint64),
            residual_bits=np.asarray(e.balance_residual_pJ).view(np.uint64),
            ieee_payloads_preserved=True,
        ),
    )


def arithmetic(name, kind, values, *, expected_valid=None):
    implementation = IMPLEMENTATIONS[kind]
    actual = arrays._balance(*values, implementation=implementation, xp=np)
    args = dict(
        zip(
            (
                "chemical_change_pJ",
                "capacitor_change_pJ",
                "clamp_work_pJ",
                "external_work_pJ",
                "dissipated_free_energy_pJ",
            ),
            values,
            strict=True,
        )
    ) | dict(family=kind)
    expected = reference.balance(**args)
    host = host_residual(*values)
    fraction = max(
        ulp_error(actual.balance_residual_pJ, host),
        ulp_error(actual.balance_residual_pJ, expected["balance_residual_pJ"]),
    )
    evidence(
        "protein-drive-arithmetic-" + name,
        dict(
            arithmetic_inputs=args,
            actual=actual._asdict(),
            expected=expected,
            host_residual_pJ=host,
            maximum_error_fraction=fraction,
        ),
    )
    assert fraction <= 1
    assert actual.physical_energy_tolerance_pJ == reference.LIMITS[kind]
    assert (
        bool(actual.checks["original_physical_energy_budget"])
        == expected["original_physical_energy_budget"]
    )
    if expected_valid is not None:
        assert bool(actual.valid) == expected_valid, actual.checks
    assert not actual.valid or expected["valid"]
    return actual


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("position", ("inside", "at", "outside"))
def test_original_family_limit_is_unchanged_at_both_signed_boundaries(kind, position):
    value = reference.LIMITS[kind]
    if position != "at":
        value = np.nextafter(value, 0.0 if position == "inside" else np.inf)
    for sign in (-1.0, 1.0):
        arithmetic(
            kind + "-" + position + "-" + str(sign),
            kind,
            (0.0, 0.0, 0.0, sign * value, 0.0),
            expected_valid=position != "outside",
        )


EXPANSIONS = (
    ("three-orders", (1.0, 2.0**-54, 1.0, 2.0**900, 2.0**900), True),
    ("missing-work", (2.0**-10, 0.0, 0.0, 2.0**900, 2.0**900), False),
    ("exact-zero", (1.0, 2.0, 3.0, 2.0**900, 2.0**900), True),
    ("negative-external", (-(2.0**-10), 0.0, 0.0, -(2.0**-10), 0.0), True),
    ("tiny-max", (7e-42, 0.0, 0.0, np.finfo(np.float64).max, np.finfo(np.float64).max), True),
    (
        "widely-separated",
        (2.0**970, -(2.0**970), -(2.0**-32), np.finfo(np.float64).max, np.finfo(np.float64).max),
        True,
    ),
)


@pytest.mark.parametrize("name,values,valid", EXPANSIONS)
def test_error_free_expansion_retains_cancelled_small_residuals(name, values, valid):
    arithmetic("expansion-" + name, "passive", values, expected_valid=valid)


TINY_NORMAL = np.finfo(np.float64).tiny
QUANTA = (
    ("subnormal-remainder", (0.0, 0.0, 0.0, np.nextafter(TINY_NORMAL, np.inf), TINY_NORMAL), False),
    ("exact-normal", (0.0, 0.0, 0.0, 2 * TINY_NORMAL, TINY_NORMAL), True),
    ("normal-remainder", (np.nextafter(-(2.0**-970), -np.inf), 0.0, 0.0, 0.0, 2.0**-970), True),
)


@pytest.mark.parametrize("name,values,valid", QUANTA)
def test_exact_quantum_guard_refuses_unresolved_subnormal_arithmetic(name, values, valid):
    actual = arithmetic("quantum-" + name, "passive", values, expected_valid=valid)
    assert bool(actual.checks["normal_expansion_quantum"]) == valid


def minimal_source():
    spec, _, _, _ = two_clamps(True)
    raw = spec.to_dict()
    model = raw["model"]
    model["cells"] = model["cells"][:1]
    model["extracellular"] = model["extracellular"][:2]
    model["membranes"] = [p for p in model["membranes"] if p["inside"] == model["cells"][0]["id"]]
    model["junctions"], model["faces"] = [], []
    names = {m["id"] for m in model["membranes"]}
    raw["experiment"]["membrane_controls"] = [
        c for c in raw["experiment"]["membrane_controls"] if c["membrane_id"] in names
    ]
    raw["experiment"]["junction_controls"] = []
    raw["execution"].update(
        capacity=2, extracellular_capacity=3, membrane_capacity=3, edge_capacity=1, face_capacity=1
    )
    spec = parse_spec(raw)
    binding = units.bind_tissue(spec, **arguments(spec, reverse=True))
    anchor = component_state(binding)
    state, layout = view.passive.initial_values(spec)
    return spec, Checkpoint(state, layout, 0.0, 0, 0), binding, anchor


@pytest.mark.parametrize("kind", ("passive", "calcium"))
def test_cpu_jax_budget_expansion_and_invalid_batched_declarations(kind):
    values = [row[1] for row in (*EXPANSIONS, *QUANTA)]
    for sign in (-1.0, 1.0):
        limit = reference.LIMITS[kind]
        for value in (np.nextafter(limit, 0), limit, np.nextafter(limit, np.inf)):
            values.append((0.0, 0.0, 0.0, sign * value, 0.0))
    expected = [
        arrays._balance(*row, implementation=IMPLEMENTATIONS[kind], xp=np) for row in values
    ]
    inputs = tuple(jnp.asarray(column) for column in zip(*values, strict=True))
    compiled = jax.jit(
        jax.vmap(lambda *a: arrays._balance(*a, implementation=IMPLEMENTATIONS[kind], xp=jnp))
    )
    actual = compiled(*inputs)
    actual.valid.block_until_ready()
    assert jax.default_backend() == "cpu" and jax.config.x64_enabled
    np.testing.assert_array_equal(actual.valid, [v.valid for v in expected])
    fraction = 0.0
    for i, target in enumerate(expected):
        if target.valid:
            fraction = max(
                fraction,
                ulp_error(float(actual.balance_residual_pJ[i]), target.balance_residual_pJ),
            )
    bad_external = inputs[3].at[0].set(jnp.nan)
    bad_dissipation = inputs[4].at[1].set(-1.0)
    refused = compiled(inputs[0], inputs[1], inputs[2], bad_external, bad_dissipation)
    refused.valid.block_until_ready()
    assert not bool(refused.valid[0]) and not bool(refused.valid[1])
    evidence(
        "protein-drive-cpu-jax-budget-" + kind,
        dict(
            valid=np.asarray(actual.valid),
            expected_valid=[v.valid for v in expected],
            residuals_pJ=np.asarray(actual.balance_residual_pJ),
            maximum_error_fraction=fraction,
            invalid_world_valid=np.asarray(refused.valid[:2]),
            worlds=len(values),
            compiled_scope=(
                "five-term budget arithmetic only; full input wrapper qualified separately"
            ),
        ),
    )
    assert fraction <= 1


def test_cpu_jax_complete_wrapper_recomputes_source_and_rejects_invalid_worlds():
    spec, point, binding, anchor = minimal_source()
    after = reservoir_transfer(spec, binding, anchor)
    pairs, expected, declarations = [], [], []
    for first, last in ((anchor, after), (after, anchor)):
        data, params = prepared(spec, point, binding, anchor, first, last)
        baseline = arrays.endpoint_work.evaluate(*data, **params, xp=np)
        dissipated = 2.0**-20
        external = math.fsum((baseline.conditional_reversible_work_pJ, dissipated))
        expected.append(
            arrays.evaluate(
                *data,
                **params,
                external_work_pJ=external,
                dissipated_free_energy_pJ=dissipated,
                budget_provenance=PROVENANCE,
                xp=np,
            )
        )
        pairs.append((data[0], data[1], data[2], data[3][3:], data[4][3:]))
        declarations.append((external, dissipated))
    shared = jax.tree.map(
        jnp.asarray, (data[3].source_state, data[3].source_control, data[3].runtime_layout)
    )
    g = jax.tree.map(jnp.asarray, data[5])

    def evaluate(a, before, after, b, e, external, dissipated):
        first = arrays.endpoint_work.endpoints.ArrayEndpoint(*shared, *b)
        last = arrays.endpoint_work.endpoints.ArrayEndpoint(*shared, *e)
        return arrays.evaluate(
            a,
            before,
            after,
            first,
            last,
            g,
            **params,
            external_work_pJ=external,
            dissipated_free_energy_pJ=dissipated,
            budget_provenance=PROVENANCE,
            xp=jnp,
        )

    batch = jax.tree.map(lambda *a: jnp.stack(a), *pairs)
    external, dissipated = (jnp.asarray(a) for a in zip(*declarations, strict=True))
    compiled = jax.jit(jax.vmap(evaluate))
    actual = compiled(*batch, external, dissipated)
    actual.valid.block_until_ready()
    assert jax.default_backend() == "cpu" and jax.config.x64_enabled
    np.testing.assert_array_equal(actual.valid, [True, True])
    bad_protein = batch[2]._replace(cell_mol_m3=batch[2].cell_mol_m3.at[0, 0].add(1e-4))
    bad_dissipation = dissipated.at[1].set(-(2.0**-20))
    bad_external = external.at[1].set(
        float(expected[1].conditional_work.conditional_reversible_work_pJ) - 2.0**-20
    )
    refused = compiled(
        batch[0], batch[1], bad_protein, batch[3], batch[4], bad_external, bad_dissipation
    )
    refused.valid.block_until_ready()
    np.testing.assert_array_equal(refused.valid, [False, False])
    np.testing.assert_array_equal(refused.conditional_work.valid, [False, True])
    assert not bool(refused.energy_balance.checks["nonnegative_declared_dissipation"][1])
    assert bool(refused.energy_balance.checks["original_physical_energy_budget"][1])
    host_errors, backend_errors = [], []
    for i, target in enumerate(expected):
        residual = float(actual.energy_balance.balance_residual_pJ[i])
        # Check the compiled sum against its own actual component quantities;
        # their NumPy/JAX energy difference has the frozen endpoint budget.
        host = host_residual(
            actual.conditional_work.chemical.total_free_energy_change_pJ[i],
            actual.conditional_work.electrical.capacitor_energy_change_pJ[i],
            actual.conditional_work.electrical.clamp_work_pJ[i],
            external[i],
            dissipated[i],
        )
        host_errors.append(ulp_error(residual, host))
        wanted = float(target.energy_balance.balance_residual_pJ)
        backend_errors.append(abs(residual - wanted) / (3e-14 + 3e-10 * abs(wanted)))
    fraction = max(*host_errors, *backend_errors)
    evidence(
        "protein-drive-cpu-jax-full-wrapper",
        dict(
            actual=report(jax.tree.map(np.asarray, actual)),
            expected=[report(x) for x in expected],
            maximum_error_fraction=fraction,
            host_arithmetic_error_fraction=host_errors,
            backend_energy_error_fraction=backend_errors,
            invalid_world_valid=np.asarray(refused.valid),
            invalid_work_valid=np.asarray(refused.conditional_work.valid),
            compiled_scope=(
                "full wrapper, one-cell/two-clamp geometry; dynamic "
                "proteins/field traces/budgets under shared fixed frame"
            ),
        ),
    )
    assert fraction <= 1
