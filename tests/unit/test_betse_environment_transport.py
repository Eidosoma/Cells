"""Native source correspondence and a separate conservative face qualification."""

import hashlib
import json
import os
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from cells.processes import betse_environment_transport as transport
from validation.transport import betse_environment_transport_reference as reference
from validation.transport.betse_environment_transport_fixtures import (
    UNIT,
    base,
    cases,
    limitations,
    refinement,
)

ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = json.loads(
    (ROOT / "validation/transport/betse_environment_transport_protocol.json").read_text()
)


def captured(name):
    folder = os.environ.get("CELLS_BETSE_ENVIRONMENT_NATIVE_CAPTURE")
    if not folder:
        pytest.skip("Bounded wrapper supplies authenticated native environment captures")
    return json.loads((Path(folder) / (name + ".json")).read_text())


def evidence(name, record):
    if folder := os.environ.get("CELLS_COMPONENT_EVIDENCE"):
        path = Path(folder)
        path.mkdir(parents=True, exist_ok=True)
        (path / ("betse-environment-transport-" + name + ".json")).write_text(
            json.dumps(record, indent=2, allow_nan=False) + "\n"
        )


def grid_spec(raw=None, *, molecule=False):
    raw = base() if raw is None else raw
    ny, nx = raw["shape"]
    h = raw["delta_m"]
    ids = tuple(raw["site_ids"])
    pairs = []
    faces = []
    b_sites = []
    b_ids = []
    b_sides = []
    for i in range(ny):
        for j in range(nx):
            at = i * nx + j
            if j + 1 < nx:
                pairs.append((ids[at], ids[at + 1]))
                faces.append(f"x:r{i}:c{j}")
            if i + 1 < ny:
                pairs.append((ids[at], ids[at + nx]))
                faces.append(f"y:r{i}:c{j}")
            for condition, side in (
                (i == 0, "S"),
                (i == ny - 1, "N"),
                (j == 0, "W"),
                (j == nx - 1, "E"),
            ):
                if condition:
                    b_sites.append(ids[at])
                    b_sides.append(side)
                    b_ids.append(f"outside:r{i}:c{j}:{side}")
    species = ("molecule:X",) if molecule else tuple(raw["species_ids"])
    z = [raw["molecule"]["valence"]] if molecule else raw["valence"]
    return transport.GridSpec(
        ids,
        species,
        np.asarray(z),
        tuple(raw["shape"]),
        np.asarray([[(j + 0.5) * h, (i + 0.5) * h] for i in range(ny) for j in range(nx)]),
        h,
        raw["height_m"],
        tuple(faces),
        tuple(pairs),
        tuple(b_ids),
        tuple(b_sites),
        tuple(b_sides),
        dict(
            native_case=raw["name"],
            source_revision=PROTOCOL["native_source"]["revision"],
            molecule=molecule,
        ),
    )


def regions(raw, grid):
    r = raw["regions"]
    return transport.Regions(
        *(
            tuple(grid.site_ids[i] for i in r[key])
            for key in ("cluster", "boundary_membrane", "neighbor_membrane", "boundary_cell")
        )
    )


def barriers(raw, grid):
    return transport.init_barriers(
        grid,
        regions(raw, grid),
        np.asarray(raw["D_free_m2_s"]),
        np.asarray(raw["relative_TJ"]),
        raw["adherens_factor"],
        raw["tight_factor"],
    )


def thermal(raw=None):
    raw = base() if raw is None else raw
    return transport.Thermal(raw["temperature_K"], raw["q_C"], raw["kb_J_K"], raw["faraday_C_mol"])


def fields(raw=None):
    raw = base() if raw is None else raw
    return transport.Fields(np.asarray(raw["electric_V_m"]), np.asarray(raw["velocity_m_s"]))


def bath_binding(raw, grid):
    return transport.compile_baths(
        grid,
        [transport.BathEvent(**v) for v in raw["events"]],
        np.asarray(raw["base_bath_mol_m3"]),
        is_ecm=raw["is_ecm"],
        enabled_Cl=raw["enabled_Cl"],
    )


def close(actual, expected, *, rtol=5e-12, atol=2e-13):
    np.testing.assert_allclose(actual, np.asarray(expected, float), rtol=rtol, atol=atol)


def face_spec(grid):
    return dict(
        site_ids=grid.site_ids,
        shape=grid.shape,
        delta_m=grid.delta_m,
        height_m=grid.height_m,
        valence=grid.kernel.valence.tolist(),
        internal_indices=list(
            zip(grid.kernel.senders.tolist(), grid.kernel.receivers.tolist(), strict=True)
        ),
        internal_normals=grid.kernel.internal_normal.tolist(),
        boundary_indices=grid.kernel.boundary_owner.tolist(),
        boundary_normals=grid.kernel.boundary_normal.tolist(),
    )


@pytest.mark.parametrize("raw", cases(), ids=lambda x: x["name"])
def test_actual_native_coefficients_baths_grid_flux_and_independent_stencils(raw):
    record = captured(raw["name"])
    grid = transport.bind_grid(grid_spec(raw))
    region = regions(raw, grid)
    expected = reference.coefficients(raw)
    native = record["coefficients"]
    targets = tuple(grid.site_ids[i] for i in expected["TJ_targets"])
    if raw["is_ecm"]:
        barrier = barriers(raw, grid)
        diffusion = barrier.diffusion_m2_s
        weight = barrier.sodium_weight
        np.testing.assert_array_equal(barrier.target_indices, native["TJ_targets"])
        close(diffusion, native["D_env"], atol=1e-25)
        close(diffusion, expected["D_env"], atol=1e-25)
        np.testing.assert_array_equal(barrier.initial_TJ_modulator, native["TJ_modulator"])
        if raw["wound"]:
            diffusion, weight = transport.wound_barriers(
                barrier,
                grid,
                tuple(grid.site_ids[i] for i in raw["wound"]["targets"]),
                raw["wound"]["factor"],
                xp=np,
            )
            close(diffusion, record["wound_coefficients"]["D_env"], atol=1e-25)
            close(weight, np.asarray(record["wound_coefficients"]["weight"]).ravel())
    else:
        diffusion = np.asarray(raw["D_free_m2_s"])
        weight = transport.legacy_non_ecm_weight(grid, region, raw["tight_factor"], xp=np)
        close(diffusion, native["D_env"], atol=1e-25)
    close(np.asarray(native["weight"]).ravel(), expected["weight"])
    if not raw["wound"]:
        close(weight, np.asarray(native["weight"]).ravel())
    chi = transport.reflect_gaussian(
        np.ones(len(grid.site_ids)) * raw["er"], grid, sigma=2.0, xp=np
    )
    close(chi, np.asarray(native["Chi"]).ravel())
    baths = bath_binding(raw, grid)
    boundary = np.asarray(raw["initial_boundary_mol_m3"])
    concentration = np.asarray(raw["concentration_mol_m3"])
    molecule = np.asarray(raw["molecule"]["initial_mol_m3"])
    total_source_change = np.zeros(len(grid.species_ids))
    for row in record["records"]:
        result = transport.apply_baths(
            row["time_s"], boundary, concentration, baths, grid, thermal(raw), xp=np
        )
        expected_bound, expected_state = reference.bath_updates(
            raw, row["time_s"], boundary.tolist(), concentration.tolist()
        )
        close(result.boundary_mol_m3, row["boundary"])
        close(result.boundary_mol_m3, expected_bound)
        close(result.field_mol_m3, row["before"])
        close(result.field_mol_m3, expected_state)
        boundary = result.boundary_mol_m3
        concentration = result.field_mol_m3
        assert transport.bath_domain_valid(
            row["time_s"], boundary, concentration, baths, grid, thermal(raw), xp=np
        )
        if raw["kind"] == "ion":
            effective = diffusion * np.asarray(raw["tj_modulator"])
            before = concentration.copy()
            update = transport.source_step(
                concentration,
                effective,
                boundary,
                fields(raw),
                thermal(raw),
                raw["dt_s"],
                grid,
                sharpness=raw["sharpness"],
                fluid_flow=raw["fluid_flow"],
                xp=np,
            )
            assert transport.source_domain_valid(
                concentration,
                effective,
                boundary,
                fields(raw),
                thermal(raw),
                raw["dt_s"],
                grid,
                sharpness=raw["sharpness"],
                fluid_flow=raw["fluid_flow"],
                xp=np,
            )
            close(update.concentration_mol_m3, row["after"])
            close(update.flux_x_mol_m2_s, row["flux_x"], atol=2e-16)
            close(update.flux_y_mol_m2_s, row["flux_y"], atol=2e-16)
            for ion in range(len(grid.species_ids)):
                oracle = reference.source_step(
                    raw,
                    concentration[ion].tolist(),
                    effective[ion].tolist(),
                    boundary[ion],
                    valence=raw["valence"][ion],
                )
                close(update.concentration_mol_m3[ion], oracle["concentration"])
                close(update.flux_x_mol_m2_s[ion].reshape(grid.shape), oracle["flux_x"], atol=2e-16)
            np.testing.assert_array_equal(concentration, before)
            change = np.sum(
                (update.concentration_mol_m3 - concentration) * grid.kernel.volume_m3, axis=-1
            )
            close(
                change,
                update.clamp_change_mol
                + update.collocated_change_mol
                + update.smoothing_change_mol,
                atol=2e-28,
            )
            total_source_change += change
            concentration = update.concentration_mol_m3
        elif raw["kind"] == "molecule":
            config = raw["molecule"]
            mg = transport.bind_grid(grid_spec(raw, molecule=True))
            d = transport.molecule_diffusivity(
                grid,
                weight,
                targets,
                config["diffusion_m2_s"],
                config["relative_TJ"],
                ignore_TJ=config["ignore_TJ"],
                xp=np,
            )
            update = transport.source_step(
                molecule[None, :],
                d[None, :],
                np.array([config["bath_mol_m3"]]),
                fields(raw),
                thermal(raw),
                raw["dt_s"],
                mg,
                sharpness=raw["sharpness"],
                fluid_flow=raw["fluid_flow"],
                extra_mobility=config["extra_mobility_m2_V_s"],
                time_dilation=config["time_dilation"],
                xp=np,
            )
            oracle = reference.source_step(
                raw,
                molecule.tolist(),
                d.tolist(),
                config["bath_mol_m3"],
                valence=config["valence"],
                mobility=config["extra_mobility_m2_V_s"],
                dilation=config["time_dilation"],
            )
            close(update.concentration_mol_m3[0], row["molecule_after"])
            close(update.concentration_mol_m3[0], oracle["concentration"])
            molecule = update.concentration_mol_m3[0]
    evidence(
        raw["name"],
        dict(
            status="passed",
            grid_identity=grid.identity,
            source_kind=raw["kind"],
            boundary_target_occurrences=len(targets),
            unique_boundary_targets=len(set(targets)),
            source_stage_amount_change_mol=total_source_change.tolist(),
            physical_face_conservation_claim=False,
        ),
    )


def simple_grid(n=4, *, species=("probe",), valence=None):
    raw = base((n, n))
    raw["delta_m"] = UNIT / n
    raw["species_ids"] = list(species)
    raw["valence"] = [0.0] * len(species) if valence is None else list(valence)
    return transport.bind_grid(grid_spec(raw))


def zero_fields(grid):
    return transport.Fields(np.zeros((2, len(grid.site_ids))), np.zeros((2, len(grid.site_ids))))


@pytest.mark.parametrize(
    "case", ("diffusion", "drift", "advection", "barrier", "zero-D-mobility", "open-bath")
)
def test_conservative_face_reference_positivity_and_species_charge_budgets(case):
    grid = simple_grid(4, species=("X", "Y"), valence=(1.0, -1.0))
    s, e = 2, len(grid.site_ids)
    b = len(grid.boundary_face_ids)
    concentration = np.array([1 + 0.2 * np.cos(np.arange(e) + i) for i in range(s)])
    diffusion = np.array([np.full(e, (i + 1) * 1e-9) for i in range(s)])
    field = zero_fields(grid)
    opened = np.zeros(b, bool)
    bath = np.ones((s, b))
    mobility = np.zeros(s)
    dt = 1e-6
    if case == "drift":
        field = field._replace(
            electric_V_m=np.array([np.linspace(-1000, 1000, e), np.ones(e) * 400])
        )
    elif case == "advection":
        field = field._replace(velocity_m_s=np.array([np.ones(e) * 1e-4, np.ones(e) * -2e-4]))
    elif case == "barrier":
        diffusion[:, [1, 5, 9, 13]] = 0
    elif case == "zero-D-mobility":
        diffusion[:] = 0
        mobility[:] = 1e-8
        field = field._replace(electric_V_m=np.array([np.ones(e) * 10, np.ones(e) * -5]))
    elif case == "open-bath":
        opened[:] = True
        bath = np.array([np.linspace(0.5, 1.5, b), np.linspace(2, 0.5, b)])
    result = transport.face_step(
        concentration,
        diffusion,
        field,
        thermal(),
        dt,
        grid,
        boundary_open=opened,
        bath_mol_m3=bath,
        mobility_m2_V_s=mobility,
        xp=np,
    )
    assert transport.face_domain_valid(
        concentration,
        diffusion,
        field,
        thermal(),
        dt,
        grid,
        boundary_open=opened,
        bath_mol_m3=bath,
        mobility_m2_V_s=mobility,
        xp=np,
    )
    oracle = reference.face_step(
        face_spec(grid),
        concentration.tolist(),
        diffusion.tolist(),
        field.electric_V_m.tolist(),
        field.velocity_m_s.tolist(),
        bath.tolist(),
        opened.tolist(),
        dt,
        thermal().temperature_K,
        thermal().elementary_charge_C,
        thermal().boltzmann_J_K,
        mobility=mobility.tolist(),
    )
    close(result.concentration_mol_m3, oracle["concentration"])
    close(result.internal_flux_mol_m2_s, oracle["internal_flux"], atol=3e-16)
    close(result.boundary_outward_flux_mol_m2_s, oracle["boundary_flux"], atol=3e-16)
    close(result.maximum_courant, oracle["maximum_courant"], atol=1e-15)
    scale = np.sum(np.abs(result.amount_change_mol), axis=-1) + np.sum(
        np.abs(result.bath_amount_change_mol), axis=-1
    )
    assert np.all(np.abs(result.balance_residual_mol) <= 3e-13 * scale)
    assert np.all(result.concentration_mol_m3 >= 0)
    assert (
        abs(result.charge_balance_residual_C)
        <= thermal().faraday_C_mol * np.sum(np.abs(grid.kernel.valence) * scale) * 3e-13
    )
    if case == "barrier":
        blocked = (diffusion[:, grid.kernel.senders] == 0) | (
            diffusion[:, grid.kernel.receivers] == 0
        )
        np.testing.assert_array_equal(result.internal_flux_mol_m2_s[blocked], 0)
    evidence(
        "conservative-" + case,
        dict(
            status="passed",
            law_id=transport.FACE_LAW_ID,
            maximum_courant=float(result.maximum_courant),
            maximum_abs_peclet=float(result.maximum_abs_peclet),
            residual_mol=result.balance_residual_mol.tolist(),
            charge_residual_C=float(result.charge_balance_residual_C),
            bath_amount_change_mol=np.sum(result.bath_amount_change_mol, axis=-1).tolist(),
        ),
    )


def test_source_and_face_conservation_checkerboard_and_boundary_limits_remain_distinct():
    raw = next(v for v in limitations() if v["name"] == "collocated-mass-defect")
    record = captured(raw["name"])
    grid = transport.bind_grid(grid_spec(raw))
    d = np.ones((4, 20)) * 1e-9
    c = np.asarray(raw["concentration_mol_m3"])
    field = zero_fields(grid)
    temp = thermal(raw)
    source = transport.source_step(c, d, np.zeros(4), field, temp, raw["dt_s"], grid, xp=np)
    close(source.concentration_mol_m3, record["records"][0]["after"])
    assert np.all(source.collocated_change_mol > 0) and np.all(source.clamp_change_mol == 0)
    # The corresponding finite-volume first step moves amount only internally;
    # perimeter site concentrations and external bath are initially zero.
    face = transport.face_step(
        c,
        d,
        field,
        temp,
        raw["dt_s"],
        grid,
        boundary_open=np.ones(len(grid.boundary_face_ids), bool),
        bath_mol_m3=np.zeros((4, len(grid.boundary_face_ids))),
        xp=np,
    )
    close(np.sum(face.amount_change_mol, axis=-1), 0, atol=1e-30)
    board = next(v for v in limitations() if v["name"] == "checkerboard-null-stencil")
    native = captured(board["name"])
    bg = transport.bind_grid(grid_spec(board))
    bc = np.asarray(board["concentration_mol_m3"])
    bd = np.ones_like(bc) * 1e-9
    moved = np.asarray(native["records"][0]["after"]).reshape(4, 8, 8)
    np.testing.assert_array_equal(moved[:, 3:-3, 3:-3], bc.reshape(4, 8, 8)[:, 3:-3, 3:-3])
    correct = transport.face_step(
        bc,
        bd,
        zero_fields(bg),
        thermal(board),
        board["dt_s"],
        bg,
        boundary_open=np.zeros(len(bg.boundary_face_ids), bool),
        bath_mol_m3=np.zeros((4, len(bg.boundary_face_ids))),
        xp=np,
    )
    assert (
        np.max(
            np.abs(
                correct.concentration_mol_m3.reshape(4, 8, 8)[:, 3:-3, 3:-3] - moved[:, 3:-3, 3:-3]
            )
        )
        > 1e-5
    )
    evidence(
        "source-defects",
        dict(
            status="passed",
            source_injected_mol=source.collocated_change_mol.tolist(),
            conservative_residual_mol=face.balance_residual_mol.tolist(),
            checkerboard_native_interior_unchanged=True,
            law_ids=[transport.SOURCE_LAW_ID, transport.FACE_LAW_ID],
        ),
    )


def test_fixed_face_bath_linear_steady_state_and_boltzmann_equilibrium():
    grid = simple_grid(8, species=("X",), valence=(1.0,))
    x = grid.coordinates_m[:, 0]
    length = UNIT
    c = (1 + x / length)[None, :]
    d = np.ones_like(c) * 1e-9
    opened = np.array([side in ("W", "E") for side in grid.boundary_face_sides])
    bath = np.array(
        [[1 if side == "W" else 2 if side == "E" else 0 for side in grid.boundary_face_sides]],
        float,
    )
    result = transport.face_step(
        c,
        d,
        zero_fields(grid),
        thermal(),
        1e-6,
        grid,
        boundary_open=opened,
        bath_mol_m3=bath,
        xp=np,
    )
    close(result.concentration_mol_m3, c, atol=2e-14)
    assert np.sum(result.bath_amount_change_mol[:, np.array(grid.boundary_face_sides) == "W"]) > 0
    assert np.sum(result.bath_amount_change_mol[:, np.array(grid.boundary_face_sides) == "E"]) < 0
    # Constant electric field and compatible bath concentration: the face law
    # exactly balances a sampled Boltzmann exponential, including half-cell ports.
    electric = 2000.0
    beta = thermal().elementary_charge_C / (thermal().boltzmann_J_K * thermal().temperature_K)
    c = np.exp(beta * electric * x)[None, :]
    bath = np.array(
        [
            [
                np.exp(beta * electric * (0 if side == "W" else length))
                if side in ("W", "E")
                else 0
                for side in grid.boundary_face_sides
            ]
        ]
    )
    field = transport.Fields(
        np.array([np.ones(len(x)) * electric, np.zeros(len(x))]), np.zeros((2, len(x)))
    )
    equilibrium = transport.face_step(
        c, d, field, thermal(), 1e-6, grid, boundary_open=opened, bath_mol_m3=bath, xp=np
    )
    close(equilibrium.internal_flux_mol_m2_s, 0, atol=2e-18)
    close(equilibrium.boundary_outward_flux_mol_m2_s, 0, atol=2e-18)
    close(equilibrium.concentration_mol_m3, c, atol=2e-14)
    evidence(
        "steady-baths",
        dict(
            status="passed",
            linear_state_stationary=True,
            boltzmann_max_flux_mol_m2_s=float(
                max(
                    np.max(np.abs(equilibrium.internal_flux_mol_m2_s)),
                    np.max(np.abs(equilibrium.boundary_outward_flux_mol_m2_s)),
                )
            ),
            field_V_m=electric,
            scope="Prescribed field and concentration; no Poisson/tissue coupling",
        ),
    )


def test_native_interior_and_conservative_spatial_and_temporal_refinement():
    native_rows = []
    for raw in refinement():
        record = captured(raw["name"])
        n = raw["shape"][0]
        div = np.asarray(
            next(v for v in record["records"][0]["trace"] if v["name"] == "divergence")["result"]
        )
        i, j = np.mgrid[:n, :n]
        signal = 0.1 * np.cos(2 * np.pi * (i + 0.5) / n) * np.cos(2 * np.pi * (j + 0.5) / n)
        true = -2e-9 * (2 * np.pi / UNIT) ** 2 * signal
        error = np.linalg.norm((div - true)[3:-3, 3:-3]) / np.linalg.norm(true[3:-3, 3:-3])
        native_rows.append(dict(n=n, relative_error=float(error)))
    native_orders = [
        float(
            np.log(native_rows[i]["relative_error"] / native_rows[i + 1]["relative_error"])
            / np.log(2)
        )
        for i in range(2)
    ]
    assert min(native_orders) > 1.8
    rows = []
    for n in (4, 8, 16):
        grid = simple_grid(n)
        i, j = np.mgrid[:n, :n]
        mode = (np.cos(np.pi * (i + 0.5) / n) * np.cos(np.pi * (j + 0.5) / n)).ravel()
        c = (1 + 0.1 * mode)[None, :]
        d = np.ones_like(c) * 1e-9
        result = transport.face_step(
            c,
            d,
            zero_fields(grid),
            thermal(),
            1e-7,
            grid,
            boundary_open=np.zeros(len(grid.boundary_face_ids), bool),
            bath_mol_m3=np.zeros((1, len(grid.boundary_face_ids))),
            xp=np,
        )
        rate = result.amount_change_mol[0] / grid.kernel.volume_m3 / 1e-7
        eigen = np.dot(mode, rate) / (0.1 * np.dot(mode, mode))
        exact = -2e-9 * (np.pi / UNIT) ** 2
        rows.append(dict(n=n, relative_error=float(abs(eigen / exact - 1))))
    orders = [
        float(np.log(rows[i]["relative_error"] / rows[i + 1]["relative_error"]) / np.log(2))
        for i in range(2)
    ]
    assert min(orders) > 1.9
    grid = simple_grid(8)
    n = 8
    i, j = np.mgrid[:n, :n]
    mode = (np.cos(np.pi * (i + 0.5) / n) * np.cos(np.pi * (j + 0.5) / n)).ravel()
    eigen = -8e-9 / grid.delta_m**2 * np.sin(np.pi / (2 * n)) ** 2
    duration = 0.2 / abs(eigen)
    time_rows = []
    opened = np.zeros(len(grid.boundary_face_ids), bool)
    bath = np.zeros((1, len(opened)))
    d = np.ones((1, n * n)) * 1e-9
    for count in (8, 16, 32):
        dt = duration / count
        c = (1 + 0.1 * mode)[None, :]
        maximum = 0.0
        for _ in range(count):
            result = transport.face_step(
                c,
                d,
                zero_fields(grid),
                thermal(),
                dt,
                grid,
                boundary_open=opened,
                bath_mol_m3=bath,
                xp=np,
            )
            c = result.concentration_mol_m3
            maximum = max(maximum, float(result.maximum_courant))
        exact = (1 + 0.1 * np.exp(eigen * duration) * mode)[None, :]
        time_rows.append(
            dict(
                steps=count,
                dt_s=dt,
                error=float(np.max(np.abs(c - exact))),
                maximum_courant=maximum,
            )
        )
    time_orders = [
        float(np.log(time_rows[i]["error"] / time_rows[i + 1]["error"]) / np.log(2))
        for i in range(2)
    ]
    assert min(time_orders) > 0.95 and max(v["maximum_courant"] for v in time_rows) < 1
    evidence(
        "refinement",
        dict(
            status="passed",
            native_interior=native_rows,
            native_interior_orders=native_orders,
            conservative_spatial=rows,
            conservative_spatial_orders=orders,
            temporal=time_rows,
            temporal_orders=time_orders,
            duration_s=duration,
            scope="Native interior only, separate sealed face cosine mode and Euler time order",
        ),
    )


def test_overlapping_bath_events_preserve_order_and_charge_defect():
    raw = next(v for v in limitations() if v["name"] == "overlapping-salt-counterion-overwrite")
    record = captured(raw["name"])
    grid = transport.bind_grid(grid_spec(raw))
    baths = bath_binding(raw, grid)
    assert tuple(v.kind for v in baths.events) == ("K_env", "Cl_env", "Na_env")
    row = record["records"][2]
    result = transport.apply_baths(
        row["time_s"],
        np.asarray(raw["initial_boundary_mol_m3"]),
        np.asarray(raw["concentration_mol_m3"]),
        baths,
        grid,
        thermal(raw),
        xp=np,
    )
    close(result.boundary_mol_m3, row["boundary"])
    assert abs(result.boundary_charge_density_change_C_m3) > 1e4
    assert transport.bath_domain_valid(
        row["time_s"],
        np.asarray(raw["initial_boundary_mol_m3"]),
        np.asarray(raw["concentration_mol_m3"]),
        baths,
        grid,
        thermal(raw),
        xp=np,
    )
    assert not transport.bath_domain_valid(
        row["time_s"],
        np.asarray(raw["initial_boundary_mol_m3"]),
        np.asarray(raw["concentration_mol_m3"]),
        baths,
        grid,
        thermal(raw),
        require_neutral_pair=True,
        xp=np,
    )
    evidence(
        "overlapping-baths",
        dict(
            status="passed",
            boundary_mol_m3=result.boundary_mol_m3.tolist(),
            charge_density_change_C_m3=float(result.boundary_charge_density_change_C_m3),
            neutral_pair_accepted=False,
        ),
    )


@pytest.mark.parametrize("raw", limitations(), ids=lambda x: x["name"])
def test_native_failures_nonconservation_and_clipping_stay_recorded(raw):
    record = captured(raw["name"])
    name = raw["name"]
    failures = {
        "missing-sodium-normalizer": "AttributeError",
        "unstable-molecule-raises": "ValueError",
        "flat-electric-field-shape": "ValueError",
        "missing-TJ-modulator": "TypeError",
        "one-row-grid": "IndexError",
        "legacy-non-ECM-missing-fields": "AttributeError",
        "zero-bath-transition": "ZeroDivisionError",
        "missing-counterion": "AttributeError",
    }
    assert record["status"] == ("captured_failure" if name in failures else "captured_limitation")
    if name in failures:
        assert record["failure_type"] == failures[name] and record["traceback"]
    if name in (
        "missing-sodium-normalizer",
        "zero-sodium-normalizer",
        "all-zero-sodium-map",
        "negative-barrier",
    ):
        grid = transport.bind_grid(grid_spec(raw))
        if name == "missing-sodium-normalizer":
            grid = transport.bind_grid(
                replace(grid_spec(raw), species_ids=("notNa", "K", "Cl", "M"))
            )
        with pytest.raises(ValueError):
            barriers(raw, grid)
    elif name == "negative-TJ-modulator":
        grid = transport.bind_grid(grid_spec(raw))
        d = barriers(raw, grid).diffusion_m2_s * np.asarray(raw["tj_modulator"])
        assert not transport.source_domain_valid(
            np.asarray(raw["concentration_mol_m3"]),
            d,
            np.asarray(raw["initial_boundary_mol_m3"]),
            fields(raw),
            thermal(raw),
            raw["dt_s"],
            grid,
            xp=np,
        )
    elif name == "unstable-ionic-Euler":
        assert np.any(np.asarray(record["clip_probe"]["unclipped"]) < 0)
        assert np.all(np.asarray(record["clip_probe"]["clipped"]) >= 0)
        assert not record["clip_probe"]["applied_by_update_ecm"]
        grid = transport.bind_grid(grid_spec(raw))
        c = np.asarray(raw["concentration_mol_m3"])
        d = barriers(raw, grid).diffusion_m2_s
        assert not transport.source_domain_valid(
            c,
            d,
            np.asarray(raw["initial_boundary_mol_m3"]),
            fields(raw),
            thermal(raw),
            raw["dt_s"],
            grid,
            xp=np,
        )
    elif name == "zero-temperature":
        grid = transport.bind_grid(grid_spec(raw))
        d = barriers(raw, grid).diffusion_m2_s
        with np.errstate(all="ignore"):
            assert not transport.source_domain_valid(
                np.asarray(raw["concentration_mol_m3"]),
                d,
                np.asarray(raw["initial_boundary_mol_m3"]),
                fields(raw),
                thermal(raw),
                raw["dt_s"],
                grid,
                xp=np,
            )
    elif name == "one-row-grid":
        with pytest.raises(ValueError, match="ny,nx"):
            transport.bind_grid(grid_spec(raw))
    elif name == "zero-bath-transition":
        grid = transport.bind_grid(grid_spec(raw))
        with pytest.raises(ValueError, match="transition"):
            bath_binding(raw, grid)
    elif name == "molecule-skips-small-bath":
        assert record["last_molecule_flux_shape"] == [[20], [20]]
        np.testing.assert_array_equal(record["records"][0]["molecule_after"], 0)
    elif name == "source-sharpness-outside-domain":
        grid = transport.bind_grid(grid_spec(raw))
        d = barriers(raw, grid).diffusion_m2_s
        assert not transport.source_domain_valid(
            np.asarray(raw["concentration_mol_m3"]),
            d,
            np.asarray(raw["initial_boundary_mol_m3"]),
            fields(raw),
            thermal(raw),
            raw["dt_s"],
            grid,
            sharpness=raw["sharpness"],
            xp=np,
        )


@pytest.mark.parametrize(
    "variant",
    (
        "duplicate-owner",
        "wrong-coordinates",
        "zero-height",
        "bad-valence",
        "missing-internal-face",
        "duplicate-face",
        "wrong-boundary-side",
        "missing-corner-face",
    ),
)
def test_invalid_grid_ownership_and_measures(variant):
    spec = grid_spec()
    if variant == "duplicate-owner":
        spec = replace(spec, site_ids=("same",) * len(spec.site_ids))
    elif variant == "wrong-coordinates":
        spec = replace(spec, coordinates_m=spec.coordinates_m[::-1])
    elif variant == "zero-height":
        spec = replace(spec, height_m=0)
    elif variant == "bad-valence":
        spec = replace(spec, valence=np.ones(4, bool))
    elif variant == "missing-internal-face":
        spec = replace(
            spec,
            internal_face_ids=spec.internal_face_ids[:-1],
            internal_face_sites=spec.internal_face_sites[:-1],
        )
    elif variant == "duplicate-face":
        spec = replace(
            spec, internal_face_sites=(spec.internal_face_sites[0],) * len(spec.internal_face_sites)
        )
    elif variant == "wrong-boundary-side":
        spec = replace(spec, boundary_face_sides=("periodic",) * len(spec.boundary_face_ids))
    else:
        spec = replace(
            spec,
            boundary_face_ids=spec.boundary_face_ids[:-1],
            boundary_face_sites=spec.boundary_face_sites[:-1],
            boundary_face_sides=spec.boundary_face_sides[:-1],
        )
    with pytest.raises(ValueError):
        transport.bind_grid(spec)


@pytest.mark.parametrize(
    "variant",
    (
        "negative-C",
        "negative-D",
        "zero-temperature",
        "large-dt",
        "invalid-field-axis",
        "integer-boundary",
        "negative-bath",
        "nan-field",
        "extreme-peclet",
    ),
)
def test_face_domain_rejects_invalid_or_nonmonotone_trials(variant):
    grid = simple_grid()
    c = np.ones((1, 16))
    d = np.ones_like(c) * 1e-9
    field = zero_fields(grid)
    temp = thermal()
    dt = 1e-6
    opened = np.zeros(len(grid.boundary_face_ids), bool)
    bath = np.zeros((1, len(opened)))
    if variant == "negative-C":
        c[0, 0] = -1
    elif variant == "negative-D":
        d[0, 0] = -1e-9
    elif variant == "zero-temperature":
        temp = temp._replace(temperature_K=0.0)
    elif variant == "large-dt":
        dt = 1.0
    elif variant == "invalid-field-axis":
        field = field._replace(electric_V_m=np.zeros(32))
    elif variant == "integer-boundary":
        opened = opened.astype(int)
    elif variant == "negative-bath":
        bath[:] = -1
    elif variant == "nan-field":
        field.electric_V_m[0, 0] = np.nan
    else:
        grid = simple_grid(valence=(1.0,))
        field = field._replace(electric_V_m=np.ones((2, 16)) * 1e8)
    with np.errstate(all="ignore"):
        assert not transport.face_domain_valid(
            c, d, field, temp, dt, grid, boundary_open=opened, bath_mol_m3=bath, xp=np
        )


def test_manifest_readonly_source_inputs_and_declared_face_permutation():
    spec = grid_spec()
    grid = transport.bind_grid(spec)
    record = transport.grid_manifest(grid)
    transport.validate_grid_manifest(json.loads(json.dumps(record)), grid)
    for v in (*grid.kernel, grid.coordinates_m):
        assert not v.flags.writeable
    with pytest.raises(ValueError):
        grid.kernel.senders[0] = 1
    other = transport.bind_grid(
        replace(
            spec,
            internal_face_ids=tuple(reversed(spec.internal_face_ids)),
            internal_face_sites=tuple((b, a) for a, b in reversed(spec.internal_face_sites)),
        )
    )
    c = np.asarray(base()["concentration_mol_m3"])
    d = np.ones_like(c) * 1e-9
    a = transport.face_step(
        c,
        d,
        zero_fields(grid),
        thermal(),
        1e-6,
        grid,
        boundary_open=np.zeros(len(grid.boundary_face_ids), bool),
        bath_mol_m3=np.zeros((4, len(grid.boundary_face_ids))),
        xp=np,
    )
    b = transport.face_step(
        c,
        d,
        zero_fields(other),
        thermal(),
        1e-6,
        other,
        boundary_open=np.zeros(len(other.boundary_face_ids), bool),
        bath_mol_m3=np.zeros((4, len(other.boundary_face_ids))),
        xp=np,
    )
    close(a.concentration_mol_m3, b.concentration_mol_m3)
    close(a.internal_flux_mol_m2_s, -b.internal_flux_mol_m2_s[:, ::-1], atol=1e-17)
    assert other.identity != grid.identity
    with pytest.raises(ValueError):
        transport.validate_grid_manifest(record, other)


def test_optional_frozen_geometry_grid_contract_and_reference_independence():
    from cells.processes import betse_geometry

    grid = transport.bind_grid(grid_spec())
    ny, nx = grid.shape
    h = grid.delta_m
    frozen = betse_geometry.bind_grid(
        betse_geometry.GridSpec(
            grid.site_ids,
            grid.shape,
            (0, nx * h, 0, ny * h),
            h,
            grid.coordinates_m,
            dict(N="flux", S="flux", E="flux", W="flux"),
            dict(source="Explicit B08 interface-only check"),
        )
    )
    np.testing.assert_array_equal(frozen.coordinates_m, grid.coordinates_m)
    close(
        grid.kernel.volume_m3,
        np.ones(len(grid.site_ids)) * frozen.delta_m**2 * grid.height_m,
        atol=1e-30,
    )
    source = (ROOT / "validation/transport/betse_environment_transport_reference.py").read_text()
    assert (
        "import numpy" not in source and "import jax" not in source and "from cells" not in source
    )
    folder = os.environ.get("CELLS_BETSE_ENVIRONMENT_NATIVE_CAPTURE")
    if not folder:
        pytest.skip("Bounded wrapper supplies native source snapshots")
    path = Path(folder)
    manifest = json.loads((path / "source-manifest.json").read_text())
    assert (
        manifest["component_cases"] == 23
        and manifest["limitations"] == 19
        and manifest["refinement_cases"] == 3
    )
    assert not manifest["production_cells_imported"] and not manifest["jax_imported"]
    assert (
        not manifest["geometry_or_cut_executed"] and not manifest["full_tissue_or_membrane_physics"]
    )
    for relative, sha in PROTOCOL["native_source"]["source_sha256"].items():
        assert hashlib.sha256((path / "upstream" / relative).read_bytes()).hexdigest() == sha
    evidence(
        "frozen-geometry-interface",
        dict(
            status="passed",
            geometry_identity=frozen.identity,
            transport_identity=grid.identity,
            geometry_rebuilt=False,
            physical_state_remapped=False,
        ),
    )


def test_cpu_jax_source_stencils_barriers_and_bath_timing():
    import jax
    import jax.numpy as jnp

    raw = base()
    grid = transport.bind_grid(grid_spec(raw))
    barrier = barriers(raw, grid)
    assert jax.config.x64_enabled and all(d.platform == "cpu" for d in jax.devices())
    c = jnp.asarray(raw["concentration_mol_m3"])
    d = jnp.asarray(barrier.diffusion_m2_s)
    b = jnp.asarray(raw["initial_boundary_mol_m3"])
    run = jax.jit(
        lambda value: transport.source_step(
            value, d, b, fields(raw), thermal(raw), raw["dt_s"], grid, sharpness=0.5
        )
    )
    actual = run(c)
    expected = transport.source_step(
        np.asarray(c),
        np.asarray(d),
        np.asarray(b),
        fields(raw),
        thermal(raw),
        raw["dt_s"],
        grid,
        sharpness=0.5,
        xp=np,
    )
    for a, e in zip(actual, expected, strict=True):
        close(a, e, atol=2e-28 if np.shape(e) == (4,) else 2e-13)
    gaussian = jax.jit(
        lambda value: transport.legacy_non_ecm_weight(grid, regions(raw, grid), 0.08)
    )(jnp.asarray(0.0))
    close(gaussian, transport.legacy_non_ecm_weight(grid, regions(raw, grid), 0.08, xp=np))
    event = transport.compile_baths(grid, [transport.BathEvent("K_env", 0.1, 0.8, 0.05, 0.4)], b)
    applied = jax.jit(lambda time: transport.apply_baths(time, b, c, event, grid, thermal(raw)))(
        jnp.asarray([0.0, 0.5])
    )
    assert applied.boundary_mol_m3.shape == (2, 4)
    for i, t in enumerate((0.0, 0.5)):
        close(
            applied.boundary_mol_m3[i],
            transport.apply_baths(
                t, np.asarray(b), np.asarray(c), event, grid, thermal(raw), xp=np
            ).boundary_mol_m3,
        )


def test_cpu_jax_conservative_batch_and_invalid_world_isolation():
    import jax
    import jax.numpy as jnp

    grid = simple_grid()
    c = np.array([1 + 0.1 * np.sin(np.arange(16))])
    d = np.ones_like(c) * 1e-9
    opened = np.ones(len(grid.boundary_face_ids), bool)
    bath = np.ones((1, len(opened)))
    worlds = np.stack((c, c, c))
    worlds[1, 0, 0] = np.nan
    valid = jax.jit(
        jax.vmap(
            lambda value: transport.face_domain_valid(
                value,
                d,
                zero_fields(grid),
                thermal(),
                1e-6,
                grid,
                boundary_open=opened,
                bath_mol_m3=bath,
            )
        )
    )(jnp.asarray(worlds))
    np.testing.assert_array_equal(valid, [True, False, True])
    actual = jax.jit(
        lambda value: transport.face_step(
            value,
            d,
            zero_fields(grid),
            thermal(),
            1e-6,
            grid,
            boundary_open=opened,
            bath_mol_m3=bath,
        )
    )(jnp.asarray(np.stack((c, c * 2))))
    for i, values in enumerate((c, c * 2)):
        expected = transport.face_step(
            values,
            d,
            zero_fields(grid),
            thermal(),
            1e-6,
            grid,
            boundary_open=opened,
            bath_mol_m3=bath,
            xp=np,
        )
        close(actual.concentration_mol_m3[i], expected.concentration_mol_m3)
    evidence(
        "jax-batches",
        dict(
            status="passed",
            valid_worlds=[True, False, True],
            shape=list(actual.concentration_mol_m3.shape),
            source_discretization_equivalence=False,
        ),
    )


def test_cpu_jax_face_operator_exact_restart_and_jacobian():
    import jax
    import jax.numpy as jnp

    grid = simple_grid()
    c = jnp.asarray([1 + 0.1 * np.cos(np.arange(16))])
    d = jnp.ones_like(c) * 1e-9
    opened = np.zeros(len(grid.boundary_face_ids), bool)
    bath = np.zeros((1, len(opened)))
    step = jax.jit(
        lambda value: (
            transport.face_step(
                value,
                d,
                zero_fields(grid),
                thermal(),
                1e-6,
                grid,
                boundary_open=opened,
                bath_mol_m3=bath,
            ).concentration_mol_m3
        )
    )

    def run(value, count):
        for _ in range(count):
            value = step(value)
        return value

    full = run(c, 8)
    resumed = run(run(c, 3), 5)
    np.testing.assert_array_equal(full, resumed)
    jac = jax.jit(jax.jacfwd(step))(c).reshape(16, 16)
    close(jnp.sum(jac, axis=0), 1, atol=2e-14)
    assert np.min(np.asarray(jac)) >= 0
    evidence(
        "jax-restart-derivative",
        dict(
            status="passed",
            steps=8,
            split=3,
            elapsed_s=8e-6,
            exact_buffers=True,
            jacobian_conservative_monotone=True,
            scope="Fixed conservative component operator only; no shared checkpoint continuation",
        ),
    )


def test_cpu_jax_fitted_zero_field_zero_diffusion_and_equilibrium_limits():
    import jax
    import jax.numpy as jnp

    grid = simple_grid(species=("X",), valence=(1.0,))
    c = jnp.ones((1, 16))
    d = jnp.zeros_like(c)
    opened = np.zeros(len(grid.boundary_face_ids), bool)
    bath = np.zeros((1, len(opened)))
    compiled = jax.jit(
        lambda value, coeff: transport.face_step(
            value,
            coeff,
            zero_fields(grid),
            thermal(),
            1e-6,
            grid,
            boundary_open=opened,
            bath_mol_m3=bath,
        )
    )
    result = compiled(c, d)
    np.testing.assert_array_equal(result.concentration_mol_m3, c)
    assert np.isfinite(np.asarray(result.internal_flux_mol_m2_s)).all()
    derivative = jax.jit(
        jax.grad(
            lambda amplitude: jnp.sum(
                compiled(c, jnp.ones_like(c) * amplitude).concentration_mol_m3
            )
        )
    )(1e-9)
    assert np.isfinite(float(derivative))
    # Removable zero-Peclet limit must also retain finite derivatives.
    electric = jnp.zeros((2, 16))

    def observed(field):
        return transport.face_step(
            c,
            jnp.ones_like(c) * 1e-9,
            transport.Fields(field, jnp.zeros_like(field)),
            thermal(),
            1e-6,
            grid,
            boundary_open=opened,
            bath_mol_m3=bath,
        ).internal_flux_mol_m2_s

    jac = jax.jit(jax.jacfwd(observed))(electric)
    assert np.isfinite(np.asarray(jac)).all()
    evidence(
        "jax-limits",
        dict(status="passed", zero_D_stationary=True, zero_field_derivatives_finite=True),
    )
