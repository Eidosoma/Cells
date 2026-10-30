"""Independent owner/Decimal unit checks for the explicit physical adapter."""

import hashlib
import json
import os
from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
from decimal import Decimal, localcontext
from pathlib import Path

import numpy as np
import pytest

from cells.core import physiology_perturbation_step as step
from cells.core import physiology_random_streams as streams
from cells.core import physiology_tissue_binding as adapter
from cells.core.specs import parse_spec
from cells.processes import betse_perturbations as perturb
from validation.tissue import surface_dynamics_fixtures as passive

ROOT = Path(__file__).resolve().parents[2]
KINDS = ("passive", "ionic", "calcium", "fuel")


def definition(kind="passive", *, padded=True, uniform=True, reorder=False):
    if kind == "passive":
        raw = passive.definition("closed", padded=padded)
    else:
        name = dict(ionic="ionic", calcium="calcium", fuel="energy")[kind]
        raw = json.loads((ROOT / ("configs/resolved_hcn_extra_" + name + ".json")).read_text())
    model = raw["model"].get("ionic", raw["model"])
    if uniform:
        for row in model["extracellular"]:
            row["volume_pL"] = 4.0
    # Each source owner/ion combination differs, exposing either axis swap.
    for j, membrane in enumerate(model["membranes"]):
        membrane["permeability_m_per_s"] = {
            species["id"]: (s + 2) * (j + 3) * 1e-10 for s, species in enumerate(model["species"])
        }
    if reorder:
        for name in ("cells", "extracellular", "membranes", "species"):
            model[name].reverse()
    raw["execution"].update(
        capacity=len(model["cells"]) + int(padded),
        extracellular_capacity=len(model["extracellular"]) + int(padded),
        membrane_capacity=len(model["membranes"]) + int(padded),
    )
    return raw


def arguments(spec, *, reverse=False):
    model = spec.model
    axes = dict(
        cell_ids=tuple(row.id for row in model.cells),
        membrane_ids=tuple(row.id for row in model.membranes),
        environment_ids=tuple(row.id for row in model.extracellular),
        ion_ids=model.species_ids,
    )
    if reverse:
        axes = {key: values[::-1] for key, values in axes.items()}
    thickness = {row.id: (j + 3) * 1e-9 for j, row in enumerate(model.membranes)}
    return axes | dict(
        membrane_thickness_m=thickness,
        boundary_cell_occurrences=(model.cells[-1].id, model.cells[0].id, model.cells[-1].id),
        provenance=dict(source="explicit synthetic unit binding", revision=1),
    )


def bind(kind="passive", *, padded=True, reverse=False, reorder=False):
    spec = parse_spec(definition(kind, padded=padded, reorder=reorder))
    return spec, adapter.bind_tissue(spec, **arguments(spec, reverse=reverse))


def evidence(name, record, arrays=None):
    if directory := os.environ.get("CELLS_COMPONENT_EVIDENCE"):
        folder = Path(directory) / "tissue-binding"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / (name + ".json")).write_text(
            json.dumps(record, indent=2, allow_nan=False, default=lambda x: np.asarray(x).tolist())
            + "\n"
        )
        if arrays is not None:
            np.savez_compressed(folder / (name + ".npz"), **arrays)


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("padded", [False, True])
@pytest.mark.parametrize("reverse", [False, True])
def test_actual_owner_geometry_and_SI_units_in_each_supported_ordinary_model(kind, padded, reverse):
    spec, binding = bind(kind, padded=padded, reverse=reverse)
    model, component = spec.model, binding.component
    membranes = {row.id: row for row in model.membranes}
    cells = {row.id: row for row in model.cells}
    outside = {row.id: row for row in model.extracellular}
    diffusion = adapter.initial_diffusion(binding)
    expected = np.empty_like(diffusion)
    with localcontext() as context:
        context.prec = 80
        for j, name in enumerate(component.membrane_ids):
            membrane = membranes[name]
            assert component.cell_ids[component.kernel.owner[j]] == membrane.inside
            assert (
                component.environment_ids[component.kernel.environment_owner[j]] == membrane.outside
            )
            assert component.kernel.membrane_area_m2[j] == membrane.area_m2
            for i, ion in enumerate(component.ion_ids):
                permeability = membrane.permeability_m_per_s[model.species_ids.index(ion)]
                expected[i, j] = float(
                    Decimal.from_float(permeability)
                    * Decimal.from_float(float(binding.membrane_thickness_m[j]))
                )
        for i, name in enumerate(component.cell_ids):
            assert component.kernel.cell_volume_m3[i] == float(
                Decimal.from_float(cells[name].volume_pL) * Decimal.from_float(1e-15)
            )
        for i, name in enumerate(component.environment_ids):
            assert component.kernel.environment_effective_volume_m3[i] == float(
                Decimal.from_float(outside[name].volume_pL) * Decimal.from_float(1e-15)
            )
    np.testing.assert_array_equal(diffusion, expected)
    assert component.environment_mode == "matrix"
    assert component.boundary_cell_occurrences == arguments(spec)["boundary_cell_occurrences"]
    assert tuple(component.kernel.boundary_cumulative_weights) == (1, 3)
    assert adapter.binding_record(
        adapter.restore_binding(adapter.binding_record(binding), spec)
    ) == (adapter.binding_record(binding))
    if kind == "fuel":
        assert not set(component.ion_ids) & {"ATP", "ADP", "Pi"}
    evidence(
        "owners-" + kind + "-" + str(padded) + "-" + str(reverse),
        dict(
            definition=spec.to_dict(),
            binding=adapter.binding_record(binding),
            independent_method="80-digit Decimal multiplication of actual named owners",
        ),
        dict(actual_diffusion=diffusion, independent_diffusion=expected),
    )


@pytest.mark.parametrize("kind", KINDS)
def test_physical_declaration_and_component_permutations_follow_IDs(kind):
    spec, binding = bind(kind, reverse=True, reorder=True)
    diffusion = adapter.initial_diffusion(binding)
    current = np.asarray(diffusion) * 1.25
    scheduled = -0.2 * diffusion
    actual = adapter.diffusion_to_permeability(
        perturb.StaticState(current, diffusion, scheduled), binding
    )
    lookup = {row.id: row for row in spec.model.membranes}
    for s in range(len(spec.model.species_ids)):
        for j, name in enumerate(binding.tissue_membrane_ids):
            expected = lookup[name].permeability_m_per_s[s]
            assert actual.base_m_s[s, j] == pytest.approx(expected, rel=3e-15, abs=0)
            assert actual.current_m_s[s, j] == pytest.approx(1.25 * expected, rel=3e-15, abs=0)
            assert actual.scheduled_m_s[s, j] == pytest.approx(-0.2 * expected, rel=3e-15, abs=0)
    for values in (actual.current_m_s, actual.base_m_s, actual.scheduled_m_s):
        np.testing.assert_array_equal(values[:, len(spec.model.membranes) :], 0)
    np.testing.assert_allclose(
        adapter.permeability_to_diffusion(actual.scheduled_m_s, binding, scheduled=True),
        scheduled,
        rtol=3e-15,
        atol=0,
    )


def component_state(binding):
    component = binding.component
    stream = streams.new_stream(
        component,
        perturb.native_stream(17),
        stream_id="explicit-tissue-component",
        world_id=7,
        next_tick=31,
    )
    controls = perturb.Controls("INIT", "normal", False, False, 0.0, 0.0, 0.002)
    diffusion = adapter.initial_diffusion(binding)
    current = perturb.static_initialize(
        diffusion, np.full(len(component.membrane_ids), 0.25), 2.0, component, xp=np
    )
    diffusion = current._replace(scheduled_m2_s=-0.25 * current.base_m2_s)
    return step.PhysiologyPerturbationState(
        perturb.ProteinState(
            np.full(len(component.cell_ids), 8.0),
            np.full(len(component.membrane_ids), 1e99),
            np.full(len(component.environment_ids), 3.0),
        ),
        diffusion,
        stream,
        controls,
        0.0,
        0,
    )


def test_component_mapping_never_draws_finalizes_advances_or_adds_protein_charge(monkeypatch):
    spec, binding = bind("fuel", reverse=True)
    state = component_state(binding)
    before = streams.stream_record(state.stream)
    raw = deepcopy(spec.to_dict())

    def forbidden(*args, **kwargs):
        pytest.fail("Binding/conversion attempted a random draw or physical loop")

    with monkeypatch.context() as guarded:
        for module, name in (
            (streams, "draw"),
            (perturb, "sample_native"),
            (perturb, "sample_stable"),
            (step, "advance"),
            (perturb, "finalize_scheduled"),
        ):
            guarded.setattr(module, name, forbidden)
        restored = adapter.restore_binding(adapter.binding_record(binding), spec)
        result = adapter.component_permeability(state, restored)
    assert streams.stream_record(state.stream) == before
    assert state.time_s == 0 and state.loop_calls == 0
    assert spec.to_dict() == raw
    potassium = spec.model.species_ids.index("K")
    np.testing.assert_allclose(
        result.current_m_s[potassium], 1.5 * result.base_m_s[potassium], rtol=3e-15, atol=0
    )
    assert not np.array_equal(result.current_m_s, result.base_m_s + result.scheduled_m_s)
    assert result.binding_identity == binding.identity


def test_native_protein_amounts_use_actual_SI_volumes_and_count_membrane_views_once():
    _, binding = bind(reverse=True)
    state = component_state(binding)
    component = binding.component
    dt, level = 0.002, 3e-8
    uniforms = np.linspace(0.15, 0.85, len(component.membrane_ids))
    result = perturb.protein_step(state.protein, uniforms, level, dt, component, xp=np)
    expected_cell = np.zeros(len(component.cell_ids))
    expected_outside = np.zeros(len(component.environment_ids))
    with localcontext() as context:
        context.prec = 80

        def d(value):
            return Decimal.from_float(float(value))

        for j in range(len(uniforms)):
            amount = float(
                d(level)
                * (d(uniforms[j]) - Decimal("0.5"))
                * d(component.kernel.membrane_area_m2[j])
                * d(dt)
            )
            expected_cell[component.kernel.owner[j]] += amount
            expected_outside[component.kernel.environment_owner[j]] -= amount
    np.testing.assert_allclose(result.cell_amount_change_mol, expected_cell, rtol=3e-15, atol=1e-38)
    np.testing.assert_allclose(
        result.environment_amount_change_mol, expected_outside, rtol=3e-15, atol=1e-38
    )
    np.testing.assert_allclose(
        (result.state.cell_mol_m3 - state.protein.cell_mol_m3) * component.kernel.cell_volume_m3,
        expected_cell,
        rtol=1e-8,
        atol=1e-30,
    )
    gross = np.sum(np.abs(expected_cell)) + np.sum(np.abs(expected_outside))
    assert abs(float(result.balance_residual_mol)) <= step.BALANCE_RELATIVE_TOLERANCE * gross
    # Huge source membrane views carry no independent material or charge.
    assert max(abs(float(x)) for x in expected_cell) < 1e-18


@pytest.mark.parametrize("kind", KINDS)
def test_original_heterogeneous_exterior_geometry_refuses_without_approximation(kind):
    spec = parse_spec(definition(kind, uniform=False))
    with pytest.raises(ValueError, match="heterogeneous actual exterior"):
        adapter.bind_tissue(spec, **arguments(spec))


def test_even_one_ULP_of_exterior_volume_heterogeneity_refuses():
    raw = definition()
    raw["model"]["extracellular"][0]["volume_pL"] = np.nextafter(4.0, np.inf)
    spec = parse_spec(raw)
    with pytest.raises(ValueError, match="heterogeneous"):
        adapter.bind_tissue(spec, **arguments(spec))


@pytest.mark.parametrize("domain", adapter.DOMAINS)
@pytest.mark.parametrize("fault", ["missing", "duplicate", "unknown"])
def test_component_axes_must_name_every_actual_owner_exactly_once(domain, fault):
    spec = parse_spec(definition())
    args = arguments(spec)
    key = domain + "_ids"
    values = list(args[key])
    if fault == "missing":
        values.pop()
    elif fault == "duplicate":
        values[-1] = values[0]
    else:
        values[-1] = "foreign_owner"
    args[key] = values
    with pytest.raises(ValueError, match="complete explicit"):
        adapter.bind_tissue(spec, **args)


@pytest.mark.parametrize(
    "fault",
    [
        "missing",
        "extra",
        "zero",
        "negative",
        "bool",
        "nan",
        "inf",
        "underflow",
        "empty_boundary",
        "foreign_boundary",
        "provenance",
    ],
)
def test_thickness_boundary_and_provenance_require_explicit_representable_declarations(fault):
    spec = parse_spec(definition())
    args = arguments(spec)
    thickness = args["membrane_thickness_m"]
    first = next(iter(thickness))
    if fault == "missing":
        del thickness[first]
    elif fault == "extra":
        thickness["foreign_membrane"] = 1e-9
    elif fault in ("zero", "negative", "bool", "nan", "inf", "underflow"):
        thickness[first] = {
            "zero": 0,
            "negative": -1,
            "bool": True,
            "nan": float("nan"),
            "inf": float("inf"),
            "underflow": np.nextafter(0.0, 1.0),
        }[fault]
    elif fault.endswith("boundary"):
        args["boundary_cell_occurrences"] = [] if fault == "empty_boundary" else ["foreign_cell"]
    else:
        args["provenance"] = {}
    with pytest.raises(ValueError):
        adapter.bind_tissue(spec, **args)


@pytest.mark.parametrize("fault", ["shape", "negative", "nonfinite", "padding", "boolean"])
def test_physical_permeability_shape_domain_and_padding_refuse(fault):
    _, binding = bind()
    values = binding.initial_permeability_m_s.copy()
    if fault == "shape":
        values = values.T
    elif fault == "negative":
        values[0, 0] = -1
    elif fault == "nonfinite":
        values[0, 0] = np.inf
    elif fault == "padding":
        values[0, -1] = 1
    else:
        values = values.astype(bool)
    with pytest.raises(ValueError):
        adapter.permeability_to_diffusion(values, binding)


def test_overflow_and_inverse_underflow_are_not_clipped_or_silently_zeroed():
    spec = parse_spec(definition())
    args = arguments(spec)
    args["membrane_thickness_m"] = {key: 1e10 for key in args["membrane_ids"]}
    binding = adapter.bind_tissue(spec, **args)
    values = binding.initial_permeability_m_s.copy()
    values[:, : len(spec.model.membranes)] = 1e300
    with pytest.raises(ValueError, match="unrepresentable"):
        adapter.permeability_to_diffusion(values, binding)
    args["membrane_thickness_m"] = {key: 1e308 for key in args["membrane_ids"]}
    binding = adapter.bind_tissue(spec, **args)
    values = np.full_like(adapter.initial_diffusion(binding), 1e-300)
    with pytest.raises(ValueError, match="unrepresentable"):
        adapter.diffusion_to_permeability(perturb.StaticState(values, values, values), binding)


def test_records_and_all_exposed_geometry_maps_and_buffers_are_immutable():
    spec, binding = bind()
    before = adapter.binding_record(binding)
    record = adapter.binding_record(binding)
    record["inputs"]["provenance"]["source"] = "changed export"
    record["geometry"]["cell_volume_m3"][0] = 999
    assert adapter.binding_record(binding) == before
    for values in (
        *binding.component.kernel,
        binding.cell_to_tissue,
        binding.membrane_to_tissue,
        binding.environment_to_tissue,
        binding.ion_to_tissue,
        binding.membrane_thickness_m,
        binding.initial_permeability_m_s,
        adapter.initial_diffusion(binding),
    ):
        with pytest.raises(ValueError):
            values.setflags(write=True)
    with pytest.raises(FrozenInstanceError):
        binding.model_id = "changed"
    with pytest.raises(ValueError, match="slot maps disagree"):
        adapter.initial_diffusion(
            replace(binding, membrane_to_tissue=binding.membrane_to_tissue[::-1])
        )
    result = adapter.component_permeability(component_state(binding), binding)
    for values in (result.current_m_s, result.base_m_s, result.scheduled_m_s):
        with pytest.raises(ValueError):
            values.setflags(write=True)
    assert adapter.binding_record(adapter.restore_binding(before, spec)) == before


@pytest.mark.parametrize("fault", ["geometry", "map", "thickness", "source", "extra_field"])
def test_even_resealed_records_rebind_actual_tissue_instead_of_trusting_cached_geometry(fault):
    spec, binding = bind()
    record = adapter.binding_record(binding)
    if fault == "geometry":
        record["geometry"]["cell_volume_m3"][0] *= 2
    elif fault == "map":
        record["slot_maps"]["cell"].reverse()
    elif fault == "thickness":
        record["membrane_thickness_m"][0] *= 2
    elif fault == "source":
        record["source_definition_sha256"] = "0" * 64
    else:
        record["hidden_field"] = "unclaimed"
    record["identity"] = hashlib.sha256(
        json.dumps(
            {k: v for k, v in record.items() if k != "identity"},
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode()
    ).hexdigest()
    with pytest.raises(ValueError, match="differs from actual"):
        adapter.restore_binding(record, spec)


def test_record_cannot_be_replayed_against_changed_physical_definition_or_component_stream():
    spec, binding = bind()
    args = arguments(spec)
    args["membrane_thickness_m"][spec.model.membranes[0].id] *= 2
    other = adapter.bind_tissue(spec, **args)
    state = component_state(binding)
    with pytest.raises(ValueError, match="another layout"):
        adapter.component_permeability(state, other)
    raw = definition()
    raw["model"]["membranes"][0]["area_m2"] *= 1.1
    with pytest.raises(ValueError, match="differs from actual"):
        adapter.restore_binding(adapter.binding_record(binding), parse_spec(raw))


@pytest.mark.parametrize(
    "fault",
    ["missing_inputs", "null_inputs", "unknown_input", "kind", "identity", "nonfinite_unit"],
)
def test_malformed_binding_replay_refuses_before_any_component_transition(fault):
    spec, binding = bind()
    record = adapter.binding_record(binding)
    if fault == "missing_inputs":
        del record["inputs"]
    elif fault == "null_inputs":
        record["inputs"] = None
    elif fault == "unknown_input":
        record["inputs"]["hidden_unit_mode"] = "approximate"
    elif fault == "kind":
        record["kind"] = "different_binding@1"
    elif fault == "identity":
        record["identity"] = "0" * 64
    else:
        record["inputs"]["membrane_thickness_m"][spec.model.membranes[0].id] = np.inf
    if fault in ("missing_inputs", "null_inputs", "unknown_input"):
        record["identity"] = hashlib.sha256(
            json.dumps(
                {k: v for k, v in record.items() if k != "identity"},
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ).encode()
        ).hexdigest()
    with pytest.raises(ValueError):
        adapter.restore_binding(record, spec)


@pytest.mark.parametrize(
    "fault", ["current_negative", "base_negative", "scheduled_nonfinite", "shape", "boolean"]
)
def test_inverse_mapping_preserves_component_current_base_and_scheduled_domain(fault):
    _, binding = bind()
    base = adapter.initial_diffusion(binding)
    values = [base.copy(), base.copy(), -0.25 * base]
    if fault == "current_negative":
        values[0][0, 0] = -1.0
    elif fault == "base_negative":
        values[1][0, 0] = -1.0
    elif fault == "scheduled_nonfinite":
        values[2][0, 0] = np.inf
    elif fault == "shape":
        values[0] = values[0].T
    else:
        values[0] = values[0].astype(bool)
    with pytest.raises(ValueError):
        adapter.diffusion_to_permeability(perturb.StaticState(*values), binding)


def test_extended_physical_subclasses_are_not_silently_admitted():
    from validation.tissue import calcium_energy_atp_transport_fixtures as atp

    spec = parse_spec(atp.probe())
    with pytest.raises(ValueError, match="exact ordinary"):
        adapter.bind_tissue(spec, **arguments(spec))
