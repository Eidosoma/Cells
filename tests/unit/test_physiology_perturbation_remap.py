"""Explicit survivor/removed protein ledgers; no geometry or sampling is inferred."""

from dataclasses import FrozenInstanceError, replace
from decimal import Decimal, localcontext

import numpy as np
import pytest

from cells.core import physiology_perturbation_remap as remap
from cells.core import physiology_perturbation_step as step
from cells.core import physiology_random_streams as streams
from cells.processes import betse_perturbations as perturb
from validation.perturbations.betse_perturbations_fixtures import base


def layout_from(raw, mode="matrix"):
    return perturb.Layout(
        tuple(raw["cell_ids"]),
        tuple(raw["membrane_ids"]),
        tuple(raw["environment_ids"]),
        tuple(raw["ion_ids"]),
        tuple(raw["cell_ids"][i] for i in raw["owner"]),
        tuple(raw["environment_ids"][i] for i in raw["environment_owner"]),
        tuple(raw["cell_ids"][i] for i in raw["boundary_cells"]),
        np.asarray(raw["membrane_area_m2"]),
        np.asarray(raw["cell_volume_m3"]),
        raw["environment_volume_m3"],
        mode,
        dict(synthetic_fixture="qualified perturbation base"),
    )


def make_state(layout, *, law="native", phase="INIT"):
    binding = perturb.bind_layout(layout)
    rng = perturb.native_stream(17) if law == "native" else perturb.StableCoordinates(17, 2**32 + 7)
    stream = streams.new_stream(
        binding, rng, stream_id="cut-component", world_id=2**32 + 7, next_tick=2**40 + 3
    )
    if law == "native":
        # An explicitly sampled Gaussian prefix tests cache preservation only;
        # no source-disabled physical microtubule update is invoked.
        _, stream = streams.draw(stream, binding, site="microtubule_gaussian")
    controls = perturb.Controls(phase, "normal", True, True, 2.0, 3e-8, 0.002)
    protein = perturb.ProteinState(
        np.asarray([8.0, 9.0, 10.0]),
        np.arange(1, len(layout.membrane_ids) + 1, dtype=float) * 1e100,
        np.arange(1, len(layout.environment_ids) + 1, dtype=float) + 3.0,
    )
    diffusion = (
        np.arange(1, len(layout.ion_ids) * len(layout.membrane_ids) + 1, dtype=float).reshape(
            len(layout.ion_ids), len(layout.membrane_ids)
        )
        * 1e-18
    )
    state = step.initialise(binding, controls, protein, diffusion, stream)
    state = replace(
        state, diffusion=state.diffusion._replace(scheduled_m2_s=-0.25 * state.diffusion.base_m2_s)
    )
    state = replace(state, time_s=0.012, loop_calls=6)
    return state, binding


@pytest.fixture
def case():
    layout = layout_from(base())
    state, binding = make_state(layout)
    return state, binding, layout


def survivor_layout(layout, *, removed=("A2",), reorder=True):
    cells = [i for i, name in enumerate(layout.cell_ids) if name not in removed]
    membranes = [i for i, cell in enumerate(layout.membrane_cell_ids) if cell not in removed]
    env, ions = list(range(len(layout.environment_ids))), list(range(len(layout.ion_ids)))
    if reorder:
        cells, membranes, env, ions = cells[::-1], membranes[::-1], env[::-1], ions[::-1]
    return replace(
        layout,
        cell_ids=tuple(layout.cell_ids[i] for i in cells),
        membrane_ids=tuple(layout.membrane_ids[i] for i in membranes),
        environment_ids=tuple(layout.environment_ids[i] for i in env),
        ion_ids=tuple(layout.ion_ids[i] for i in ions),
        membrane_cell_ids=tuple(layout.membrane_cell_ids[i] for i in membranes),
        membrane_environment_ids=tuple(layout.membrane_environment_ids[i] for i in membranes),
        cell_volume_m3=layout.cell_volume_m3[cells],
        membrane_area_m2=layout.membrane_area_m2[membranes],
        boundary_cell_occurrences=tuple(
            name for name in layout.boundary_cell_occurrences if name not in removed
        ),
    )


def without_sampling(state, old, new, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("A pure remap attempted to consume a random draw")

    with monkeypatch.context() as guarded:
        guarded.setattr(streams, "draw", forbidden)
        guarded.setattr(perturb, "sample_native", forbidden)
        guarded.setattr(perturb, "sample_stable", forbidden)
        return remap.remap_component(state, old, new)


def record(state, binding):
    return perturb.replay_record(
        binding,
        state.controls,
        perturb.Replay(
            state.protein, state.diffusion, state.stream.rng, state.stream.next_tick, state.time_s
        ),
    ) | dict(stream=streams.stream_record(state.stream), loop_calls=state.loop_calls)


def test_complete_survivors_and_removed_views_follow_explicit_ids(case, monkeypatch):
    state, old, layout = case
    new = perturb.bind_layout(survivor_layout(layout))
    before = record(state, old)
    result = without_sampling(state, old, new, monkeypatch)
    expected = dict(cell=[2, 0], membrane=[5, 4, 2, 1], environment=[3, 2, 1, 0], ion=[2, 1, 0])
    for domain in expected:
        assert result.diagnostics[domain + "_new_to_old"] == tuple(expected[domain])
    for actual, original, domain in zip(
        result.state.protein, state.protein, ("cell", "membrane", "environment"), strict=True
    ):
        np.testing.assert_array_equal(actual, original[expected[domain]])
    for actual, original in zip(result.state.diffusion, state.diffusion, strict=True):
        np.testing.assert_array_equal(
            actual, original[np.ix_(expected["ion"], expected["membrane"])]
        )
    assert result.state.controls is state.controls
    assert result.state.time_s == state.time_s and result.state.loop_calls == state.loop_calls
    assert result.state.stream.rng == state.stream.rng
    assert result.state.stream.next_tick == state.stream.next_tick
    assert result.state.stream.world_id == state.stream.world_id
    assert result.state.stream.stream_id == state.stream.stream_id
    assert result.state.stream.layout_identity == new.identity
    assert result.archive.cell_ids == ("A2",)
    assert result.archive.membrane_ids == ("m8", "m1", "m6")
    assert result.archive.environment_ids == () and result.archive.ion_ids == old.ion_ids
    np.testing.assert_array_equal(
        result.archive.protein.cell_mol_m3, state.protein.cell_mol_m3[[1]]
    )
    np.testing.assert_array_equal(
        result.archive.protein.membrane_mol_m3, state.protein.membrane_mol_m3[[0, 3, 6]]
    )
    assert result.archive.protein.environment_mol_m3.shape == (0,)
    for actual, original in zip(result.archive.diffusion, state.diffusion, strict=True):
        np.testing.assert_array_equal(actual, original[:, [0, 3, 6]])
    assert record(state, old) == before


def test_removed_amounts_match_Decimal_density_measure_and_exclude_membrane_views(
    case, monkeypatch
):
    state, old, layout = case
    result = without_sampling(state, old, perturb.bind_layout(survivor_layout(layout)), monkeypatch)
    with localcontext() as context:
        context.prec = 80
        amount = float(
            Decimal.from_float(float(state.protein.cell_mol_m3[1]))
            * Decimal.from_float(float(old.kernel.cell_volume_m3[1]))
        )
    assert result.archive.cell_amount_mol.tolist() == [amount]
    assert result.archive.total_amount_mol == amount
    assert result.diagnostics["removed_amount_mol"] == amount
    assert result.diagnostics["partition_residual_mol"] == 0.0
    assert result.diagnostics["membrane_views_are_material"] is False
    assert np.min(result.archive.protein.membrane_mol_m3) >= 1e100
    assert amount < 1e-14  # Huge membrane readout buffers are never another inventory.
    assert result.archive.environment_amount_mol.shape == (0,)


def test_noop_keeps_state_identity_and_empty_archives_have_complete_shapes(case, monkeypatch):
    state, old, _ = case
    result = without_sampling(state, old, old, monkeypatch)
    assert result.state is state
    assert result.archive.cell_ids == result.archive.membrane_ids == ()
    assert result.archive.protein.cell_mol_m3.shape == (0,)
    assert result.archive.protein.membrane_mol_m3.shape == (0,)
    for value in result.archive.diffusion:
        assert value.shape == (len(old.ion_ids), 0)
    assert result.archive.total_amount_mol == result.diagnostics["removed_amount_mol"] == 0.0
    assert result.diagnostics["draws_consumed"] == 0


def test_pure_reorder_preserves_all_material_and_archives_nothing(case, monkeypatch):
    state, old, layout = case
    new = perturb.bind_layout(survivor_layout(layout, removed=()))
    result = without_sampling(state, old, new, monkeypatch)
    assert result.archive.total_amount_mol == 0.0
    assert result.diagnostics["retained_amount_mol"] == result.diagnostics["previous_amount_mol"]
    for domain in ("cell", "membrane", "environment", "ion"):
        assert result.diagnostics[domain + "_new_to_old"] == tuple(
            range(len(getattr(old, domain + "_ids")) - 1, -1, -1)
        )


@pytest.mark.parametrize("law", ["native", "stable"])
def test_future_packets_preserve_each_qualified_law_without_native_subset_claim(
    case, law, monkeypatch
):
    _, _, layout = case
    state, old = make_state(layout, law=law)
    new = perturb.bind_layout(survivor_layout(layout))
    result = without_sampling(state, old, new, monkeypatch)
    packet, after = streams.draw(result.state.stream, new, site="protein_flux")
    if law == "stable":
        full, _ = streams.draw(state.stream, old, site="protein_flux")
        np.testing.assert_array_equal(packet.values, full.values[[5, 4, 2, 1]])
    else:
        assert perturb.native_stream_manifest(state.stream.rng)["state"][3] == 1
        target, rng = perturb.sample_native(
            state.stream.rng, new, site="protein_flux", tick=state.stream.next_tick
        )
        assert perturb.draw_manifest(packet, new) == perturb.draw_manifest(target, new)
        assert after.rng == rng
        full, _ = streams.draw(state.stream, old, site="protein_flux")
        assert not np.array_equal(packet.values, full.values[[5, 4, 2, 1]])
    assert packet.tick == state.stream.next_tick


def test_explicit_postcut_component_call_uses_preserved_state_with_new_binding(case, monkeypatch):
    state, old, layout = case
    state = replace(state, controls=replace(state.controls, phase="SIM"))
    new = perturb.bind_layout(survivor_layout(layout))
    result = without_sampling(state, old, new, monkeypatch)
    transition = step.advance(result.state, new)
    assert transition.state.time_s == state.time_s + state.controls.dt_s
    assert transition.state.loop_calls == state.loop_calls + 1
    assert transition.state.stream.next_tick == state.stream.next_tick + 1
    assert transition.packet.layout_identity == new.identity


def test_archive_and_remapped_state_are_immutable_and_cannot_alias_input(case, monkeypatch):
    state, old, layout = case
    result = without_sampling(state, old, perturb.bind_layout(survivor_layout(layout)), monkeypatch)
    for value in (
        *result.archive.protein,
        *result.archive.diffusion,
        result.archive.cell_volume_m3,
        result.archive.membrane_area_m2,
        result.archive.cell_amount_mol,
    ):
        with pytest.raises(ValueError):
            value.setflags(write=True)
    with pytest.raises(FrozenInstanceError):
        result.archive.cell_ids = ()
    assert not np.shares_memory(result.state.protein.cell_mol_m3, state.protein.cell_mol_m3)


@pytest.mark.parametrize("field", ["cell_volume", "membrane_area", "environment_volume", "mode"])
def test_geometry_volume_and_mode_changes_are_refused(case, field, monkeypatch):
    state, old, layout = case
    new = survivor_layout(layout)
    if field == "cell_volume":
        new = replace(new, cell_volume_m3=np.nextafter(new.cell_volume_m3, np.inf))
    elif field == "membrane_area":
        new = replace(new, membrane_area_m2=np.nextafter(new.membrane_area_m2, np.inf))
    elif field == "environment_volume":
        new = replace(
            new,
            environment_parameter_volume_m3=np.nextafter(
                new.environment_parameter_volume_m3, np.inf
            ),
        )
    else:
        new = replace(new, environment_mode="source_fast")
    with pytest.raises(ValueError, match="geometry/volume|environment mode"):
        without_sampling(state, old, perturb.bind_layout(new), monkeypatch)


def test_geometry_precision_change_refuses_even_if_values_are_equal(case, monkeypatch):
    _, _, layout = case
    layout = replace(layout, cell_volume_m3=np.asarray([1.0, 2.0, 4.0]))
    state, old = make_state(layout)
    new = survivor_layout(layout)
    new = replace(new, cell_volume_m3=new.cell_volume_m3.astype(np.float32))
    with pytest.raises(ValueError, match="precision"):
        without_sampling(state, old, perturb.bind_layout(new), monkeypatch)


@pytest.mark.parametrize(
    "defect",
    [
        "ion_loss",
        "environment_loss",
        "partial_membrane",
        "foreign_membrane",
        "reassigned_owner",
        "terminal",
    ],
)
def test_unsupported_or_foreign_owner_operations_refuse(case, defect, monkeypatch):
    state, old, layout = case
    new = survivor_layout(layout)
    if defect == "ion_loss":
        new = replace(new, ion_ids=new.ion_ids[:-1])
    elif defect == "environment_loss":
        new = replace(
            new, environment_ids=tuple(name for name in new.environment_ids if name != "env9")
        )
    elif defect == "partial_membrane":
        new = replace(
            new,
            membrane_ids=new.membrane_ids[1:],
            membrane_cell_ids=new.membrane_cell_ids[1:],
            membrane_environment_ids=new.membrane_environment_ids[1:],
            membrane_area_m2=new.membrane_area_m2[1:],
        )
    elif defect == "foreign_membrane":
        new = replace(new, membrane_ids=("new-wound", *new.membrane_ids[1:]))
    elif defect == "reassigned_owner":
        new = replace(new, membrane_cell_ids=("C7", *new.membrane_cell_ids[1:]))
    else:
        with pytest.raises(ValueError, match="Terminal"):
            without_sampling(state, old, replace(old, cell_ids=()), monkeypatch)
        return
    with pytest.raises(ValueError):
        without_sampling(state, old, perturb.bind_layout(new), monkeypatch)


def test_mixed_bath_effective_volume_change_is_not_hidden_by_concentration_copy(case, monkeypatch):
    _, _, layout = case
    layout = replace(
        layout,
        environment_ids=("bath",),
        membrane_environment_ids=("bath",) * len(layout.membrane_ids),
        environment_mode="mixed_bath",
    )
    state, old = make_state(layout)
    new = perturb.bind_layout(survivor_layout(layout))
    assert (
        old.kernel.environment_effective_volume_m3[0]
        != new.kernel.environment_effective_volume_m3[0]
    )
    with pytest.raises(ValueError, match="environment_effective_volume"):
        without_sampling(state, old, new, monkeypatch)


@pytest.mark.parametrize(
    "defect",
    ["invalid_state", "stale_old_binding", "unrepresentable_amount", "unrepresentable_total"],
)
def test_invalid_source_and_nonrepresentable_stock_refuse_without_sampling(
    case, defect, monkeypatch
):
    state, old, layout = case
    if defect == "invalid_state":
        state = replace(
            state, protein=state.protein._replace(cell_mol_m3=-state.protein.cell_mol_m3)
        )
    elif defect == "stale_old_binding":
        old = replace(old, identity="0" * 64)
    elif defect == "unrepresentable_amount":
        layout = replace(layout, cell_volume_m3=np.asarray([1e100] * 3))
        state, old = make_state(layout)
        state = replace(state, protein=state.protein._replace(cell_mol_m3=np.full(3, 1e300)))
    else:
        layout = replace(
            layout, cell_volume_m3=np.full(3, 2e307), environment_parameter_volume_m3=3e307
        )
        state, old = make_state(layout)
        state = replace(
            state,
            protein=state.protein._replace(
                cell_mol_m3=np.full(3, 2.0), environment_mol_m3=np.ones(4)
            ),
        )
    new = perturb.bind_layout(survivor_layout(layout))
    with pytest.raises(ValueError):
        without_sampling(state, old, new, monkeypatch)
