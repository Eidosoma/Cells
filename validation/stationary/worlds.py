"""Worlds for the stationary-analysis targets (stationary_continuation_analysis@1).

default_world_cell(): one well-mixed cell facing a held bath with the heredity
pre-screen's BETSE v1.5.0 default-world coefficients (the "world" block of
/mnt/workspaces/Cells/heredity-design-20261108-01/prescreen-03.json: volume,
area, Dm/tm permeabilities, pump capacity 1e-7 mol/m^2/s x area, cm 0.05 F/m^2,
bath Na 145, K 5, M 140, P 10 mM, impermeant intracellular anion P 135 mM, 310 K,
fixed volume), declared as resolved_pump_tissue@1 (no channel population).

The pre-screen's slow model takes the cell's charge as F vol (Na + K - M - P)
with nothing else fixed, so the cell here carries no further background charge
(fixed_charge_equivalent_fmol = 0) and its initial charge is that ionic charge:
this is the pre-screen's world exactly, not a world tuned to one state.
"""

import copy
import json
import math
from pathlib import Path

from cells.processes.electrochemistry import CHARGE_PER_FMOL

PRESCREEN = Path("/mnt/workspaces/Cells/heredity-design-20261108-01")
SPECIES = (("Na", 1), ("K", 1), ("M", -1), ("P", -1))
BATH_mM = dict(Na=145.0, K=5.0, M=140.0, P=10.0)
FIXED_ANION_mM = 135.0
TEMPERATURE_K = 310.0
PUMP = dict(
    law="nak_atp_mass_action_positive@1",
    roles=dict(sodium="Na", potassium="K"),
    stoichiometry=dict(Na=-3, K=2),
    km_na_mM=12.0,
    km_k_mM=0.2,
    km_atp_mM=0.5,
    metabolism=dict(
        kind="maintained_chemical_reservoirs@1",
        atp_mM=1.5,
        adp_mM=0.1,
        pi_mM=0.1,
        delta_g0_J_per_mol=-37000.0,
    ),
)


# The "world" block of prescreen-03.json (BETSE v1.5.0 default-world extraction:
# mean cell volume and patch area, Dm/tm with tm 7.5 nm, alpha_NaK 1e-7 mol/m^2/s
# x area, cm 0.05 F/m^2) and its INIT-end composition; prescreen_world() reads
# the saved record so a driver can check these values against it.
DEFAULT_WORLD = dict(
    volume_m3=7.505222518670602e-16,
    area_m2=3.261272165616906e-10,
    capacitance_F=1.6306360828084532e-11,
    permeability_m_s=dict(
        Na=2.666666666666668e-10, K=1.333333333333334e-10, M=1.333333333333334e-10
    ),
    pump_capacity_fmol_s=0.032612721656169054,
    init_end=dict(
        Na=11.874721829067255, K=139.1397016205685, M=16.019763503217945, vm_V=-0.02332361445899843
    ),
)


def prescreen_world(path=PRESCREEN / "prescreen-03.json"):
    """The pre-screen's saved world block (frozen evidence, read only)."""
    return json.loads(Path(path).read_text())["world"]


def ionic_charge_C(amounts_fmol):
    """The pre-screen's cell charge: F times the valence-weighted amounts."""
    z = dict(SPECIES)
    return CHARGE_PER_FMOL * math.fsum(z[s] * amounts_fmol[s] for s, _ in SPECIES)


def default_world_cell(
    composition_mM=None,
    *,
    na_scale=1.0,
    dt=1e-3,
    end_time=1.0,
    observation_times=None,
    solver="imex_ars222_face_electromigration@1",
    world=None,
):
    """resolved_pump_tissue@1 definition of the pre-screen's default-world cell.

    composition_mM: initial (Na, K, M) in mM, default the record's INIT end.
    """
    w = DEFAULT_WORLD if world is None else world
    if composition_mM is None:
        e = w["init_end"]
        composition_mM = (e["Na"], e["K"], e["M"])
    volume_pL = w["volume_m3"] * 1e15
    na, k, mm = composition_mM
    amounts = {
        s: c * volume_pL
        for s, c in zip(("Na", "K", "M", "P"), (na, k, mm, FIXED_ANION_mM), strict=True)
    }
    ids = [s for s, _ in SPECIES]
    permeability = dict(w["permeability_m_s"])
    permeability["Na"] *= na_scale
    permeability["P"] = 0.0
    times = [0.0, end_time] if observation_times is None else list(observation_times)
    always = [dict(time=0.0, availability=1.0)]
    return dict(
        schema_version=1,
        model=dict(
            id="resolved_pump_tissue@1",
            temperature_K=TEMPERATURE_K,
            species=[dict(id=s, valence=v) for s, v in SPECIES],
            cells=[
                dict(
                    id="cell_0",
                    volume_pL=volume_pL,
                    initial_amount_fmol=amounts,
                    fixed_charge_equivalent_fmol=0.0,
                    initial_charge_C=ionic_charge_C(amounts),
                )
            ],
            extracellular=[
                dict(
                    id="bath_0",
                    volume_pL=1.0,
                    initial_amount_fmol=dict(BATH_mM),
                    fixed_charge_equivalent_fmol=-math.fsum(z * BATH_mM[s] for s, z in SPECIES),
                    initial_charge_C=0.0,
                    reservoir=True,
                    boundary_potential_V=0.0,
                )
            ],
            membranes=[
                dict(
                    id="membrane_0",
                    inside="cell_0",
                    outside="bath_0",
                    area_m2=w["area_m2"],
                    capacitance_F=w["capacitance_F"],
                    permeability_m_per_s={s: permeability[s] for s in ids},
                    law="constant_field@1",
                    pump=dict(
                        id="pump_0",
                        capacity_fmol_per_s=w["pump_capacity_fmol_s"],
                        **copy.deepcopy(PUMP),
                    ),
                )
            ],
            junctions=[],
            faces=[],
            closure=dict(
                law="resolved_capacitor_components_current_continuity@1", gauge_reference=None
            ),
        ),
        experiment=dict(
            end_time=end_time,
            observation_times=times,
            membrane_controls=[dict(membrane_id="membrane_0", schedule=copy.deepcopy(always))],
            junction_controls=[],
            pump_controls=[dict(pump_id="pump_0", schedule=copy.deepcopy(always))],
        ),
        execution=dict(
            dt=dt,
            capacity=1,
            extracellular_capacity=1,
            membrane_capacity=1,
            edge_capacity=0,
            face_capacity=0,
            backend="cpu",
            jit=True,
            precision="float64",
            solver=solver,
            field_solver="capacitive_reduction_gauged_damped_newton@2",
            max_steps=int(math.ceil(end_time / dt)) + 8,
            max_trace_bytes=2**31,
            material_balance_atol_fmol={s: 1e-10 for s in ids},
        ),
    )


# ------------------------------------------------- resolved_pump_tissue@3 worlds


def ionic_background(raw):
    """Give every cell of a heredity definition the pre-screen's background.

    validation/tissue/surface_pump_v3_fixtures.heredity_cells sets each cell's
    fixed background so that its charge is C Vm for the declared Vm (absorbing
    the pre-screen's root residual). The reduced models instead take the charge
    as F vol (Na + K - M - P) with P the only fixed charge. This sets the fixed
    background to zero and the charge to that ionic charge, in place.
    """
    for cell in raw["model"]["cells"]:
        cell["fixed_charge_equivalent_fmol"] = 0.0
        cell["initial_charge_C"] = ionic_charge_C(cell["initial_amount_fmol"])
    return raw


def hexagon(radius):
    """Axial coordinates of a hexagonal sheet (3 r (r + 1) + 1 cells) and its edges."""
    cells = [
        (q, r)
        for q in range(-radius, radius + 1)
        for r in range(-radius, radius + 1)
        if abs(q + r) <= radius
    ]
    index = {c: i for i, c in enumerate(cells)}
    edges = []
    for (q, r), i in index.items():
        for dq, dr in ((1, 0), (0, 1), (-1, 1)):
            j = index.get((q + dq, r + dr))
            if j is not None:
                edges.append((i, j))
    return cells, edges


def ring(cell):
    q, r = cell
    return max(abs(q), abs(r), abs(q + r))


def e07_junction():
    """The E07-v1 (W225) junction: BETSE v1.5.0 default gap-junction coefficients.

    From validation/tissue/resolved_scale_world.py: area = the cell's patch area
    (spacing / sqrt(3) x height), permeability = free diffusivity x gap-junction
    surface fraction / length per species (P blocked), and the voltage gate
    junction_voltage_relaxation@1 with threshold 15 mV and minimum 0.1.
    """
    from validation.tissue import resolved_scale_world as w225

    species = [s for s, _ in w225.SPECIES]
    permeability = {
        s: d * w225.GJ_SURFACE_FRACTION / w225.GJ_LENGTH_m
        for s, d in zip(species, w225.FREE_D_m2_s, strict=True)
    }
    return dict(
        area_m2=w225.geometry()["patch_area"],
        permeability_m_per_s={s: permeability[s] for s, _ in SPECIES},
        threshold_voltage_V=w225.GJ_THRESHOLD_V,
        minimum_open_fraction=w225.GJ_MINIMUM,
    )


def lognormal_factors(count, cv, rng):
    """Mean-one lognormal multipliers with coefficient of variation cv."""
    import numpy as np

    sigma = np.sqrt(np.log1p(cv * cv))
    return np.exp(rng.normal(-0.5 * sigma * sigma, sigma, size=count))


def e07_heterogeneity(cells, edges, *, seed, cell_cv, junction_cv):
    """Per-cell NaV1.2, Kir2.1, Na-leak and pump factors and per-junction factors.

    E07-v1's description (design.json protocol.world.heterogeneity): per cell
    lognormal CV on NaV, Kir, Na leak and pump capacity; per junction CV on
    permeability. Drawn here from numpy's default generator with the seed.
    """
    import numpy as np

    rng = np.random.default_rng(seed)
    keys = ("nav", "kir", "na_leak", "pump")
    draws = {k: lognormal_factors(cells, cell_cv, rng) for k in keys}
    cell_factors = [{k: float(draws[k][i]) for k in keys} for i in range(cells)]
    return cell_factors, [float(v) for v in lognormal_factors(edges, junction_cv, rng)]


def e07_sheet_definition(
    states,
    edges,
    *,
    scale=1.0,
    gated=True,
    dt=1e-3,
    end_time=1.0,
    cell_factors=None,
    junction_factors=None,
):
    """Heredity cells (own held baths) joined by E07-v1 junctions at scale x the W225 values.

    gated: the voltage gate as declared, each gate starting at its steady state
    for the cells' declared voltages; otherwise the gate is held open (minimum
    open fraction 1, threshold 0, gate 1). cell_factors (per cell: nav, kir,
    na_leak, pump) and junction_factors (per edge) multiply the corresponding
    permeabilities and pump capacity (e07_heterogeneity).
    """
    import numpy as np

    from cells.processes import junction_gate
    from validation.morphogenesis import mg0b_domain_wall as wall
    from validation.tissue import surface_pump_v3_fixtures as fixtures

    j = e07_junction()
    raw = fixtures.heredity_cells(
        list(states),
        dt=dt,
        end_time=end_time,
        solver=wall.SOLVER,
        observation_times=[0.0, end_time],
        gate_voltages=[s[0] for s in states],
    )
    m, e, x = raw["model"], raw["experiment"], raw["execution"]
    if cell_factors is not None:
        channels = {c["id"]: c for c in m["channels"]}
        for i, f in enumerate(cell_factors):
            channels[f"nav_{i}"]["max_permeability_m_per_s"] *= f["nav"]
            channels[f"kir_{i}"]["max_permeability_m_per_s"] *= f["kir"]
            m["membranes"][i]["permeability_m_per_s"]["Na"] *= f["na_leak"]
            m["membranes"][i]["pump"]["capacity_fmol_per_s"] *= f["pump"]
    factors = [1.0] * len(edges) if junction_factors is None else list(junction_factors)
    parameters = junction_gate.Parameters(j["threshold_voltage_V"], j["minimum_open_fraction"])
    junctions = []
    for k, (a, b) in enumerate(edges):
        if gated:
            vj = np.asarray(states[a][0] - states[b][0])
            target = float(junction_gate.kinetics(vj, parameters, xp=np).target)
            gate = dict(
                law=junction_gate.LAW_ID,
                threshold_voltage_V=j["threshold_voltage_V"],
                minimum_open_fraction=j["minimum_open_fraction"],
                initial_gate=target,
            )
        else:
            gate = dict(wall.GATE_OPEN)
        junctions.append(
            dict(
                id=f"junction_{k}",
                sender=f"cell_{a}",
                receiver=f"cell_{b}",
                area_m2=j["area_m2"],
                permeability_m_per_s={
                    s: scale * factors[k] * v for s, v in j["permeability_m_per_s"].items()
                },
                law="constant_field@1",
                gate=gate,
            )
        )
    m["junctions"] = junctions
    e["junction_controls"] = [
        dict(junction_id=f"junction_{k}", schedule=[dict(time=0.0, availability=1.0)])
        for k in range(len(edges))
    ]
    x["edge_capacity"] = len(edges)
    return raw


def sheet_definition(
    states,
    edges,
    junction_m_s,
    *,
    nav_availability=1.0,
    control=None,
    gate_voltages=None,
    dt=1e-3,
    end_time=1.0,
):
    """Heredity cells (own held baths) joined by open-gated linear junctions.

    states: (Vm, Na, K, M) per cell; edges: (i, j) cell pairs. The junctions are
    those of the MG0b driver (validation/morphogenesis/mg0b_domain_wall.py):
    constant_field@1 for Na, K and M, P blocked, the voltage gate held open.
    nav_availability holds every NaV1.2 population's availability; control, if
    given, adds the MG0b control population (Na leak, CONTROL_M_S) to every
    cell at that availability.
    """
    from validation.morphogenesis import mg0b_domain_wall as wall
    from validation.tissue import surface_pump_v3_fixtures as fixtures

    raw = fixtures.heredity_cells(
        list(states),
        dt=dt,
        end_time=end_time,
        solver=wall.SOLVER,
        observation_times=[0.0, end_time],
        gate_voltages=gate_voltages,
    )
    m, e, x = raw["model"], raw["experiment"], raw["execution"]
    for group in e["channel_controls"]:
        if group["channel_id"].startswith("nav_"):
            group["schedule"] = [dict(time=0.0, availability=float(nav_availability))]
    if control is not None:
        for i in range(len(states)):
            m["channels"].append(
                fixtures.channel(
                    f"ctrl_{i}", i, wall.NALEAK_LAW_ID, "Na", wall.CONTROL_M_S, 1.0, []
                )
            )
            e["channel_controls"].append(
                dict(channel_id=f"ctrl_{i}", schedule=[dict(time=0.0, availability=float(control))])
            )
        x["channel_capacity"] = len(m["channels"])
    m["junctions"] = [
        dict(
            id=f"junction_{k}",
            sender=f"cell_{i}",
            receiver=f"cell_{j}",
            area_m2=wall.JUNCTION_AREA_M2,
            permeability_m_per_s={
                s: (junction_m_s if s in wall.JUNCTION_SPECIES else 0.0) for s, _ in SPECIES
            },
            law="constant_field@1",
            gate=dict(wall.GATE_OPEN),
        )
        for k, (i, j) in enumerate(edges)
    ]
    e["junction_controls"] = [
        dict(junction_id=f"junction_{k}", schedule=[dict(time=0.0, availability=1.0)])
        for k in range(len(edges))
    ]
    x["edge_capacity"] = len(edges)
    return raw
