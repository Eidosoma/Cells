"""resolved_pump_water@1 worlds: resolved_pump_tissue@3 definitions with a water block.

with_water(raw, ...) declares water on a resolved_pump_tissue@3 definition: every
cell and finite outside node becomes a compliant compartment, every reservoir a
held bath, every membrane a water route. The default parameters are the approved
heredity water-arm values (docs/PUMP_WATER_MODEL.md, each with its source):

* osmotic permeability Pf 3e-3 cm/s at 310 K without aquaporins (cells without
  aquaporins 0.5-7e-3 cm/s at 10-25 C: Farinas et al. 1997 J Gen Physiol
  110:283; Mathai et al. 1996 J Biol Chem 271:1309; Yang & Verkman 2002 J Biol
  Chem 277:36782; Solenov et al. 2004 Am J Physiol Cell Physiol 286:C426; scaled
  to 37 C by the lipid-path activation energy), Lp = Pf Vw / (R T) (Manning &
  Kay 2023 J Gen Physiol 155:e202313332, Eq. 6);
* modulus K = 60 Pa (elastic cortex, K = (4/3) E h / R with E h = 240 Pa um,
  Tinevez et al. 2009 PNAS 106:18581) and pressure offset P0 = 40 Pa
  (interphase HeLa, Fischer-Friedrich et al. 2014 Sci Rep 4:6213);
* volume bounds 0.5 V0 and 2 V0 (below 2x, swelling is taken up by shape change
  and membrane reserves, Groulx et al. 2006 J Membr Biol 214:43; 0.5 V0 is a
  declared validity choice of the ideal-solution law);
* no neutral impermeants beyond the declared species (the P species carries the
  impermeant osmolytes); baths at hydrostatic pressure 0.

availability: every route's water availability from t = 0 (0 closes water while
keeping the full water code path), or a schedule [(time, availability), ...].
"""

import copy

MOLAR_VOLUME_WATER_M3_MOL = 18.07e-6  # 18.015 g/mol / 0.997 g/cm^3 (25 C).
GAS_CONSTANT = 8.314462618  # J/(mol K), as cells.processes.electrochemistry.R.
NO_AQUAPORIN_PF_M_S = 3e-5  # 3e-3 cm/s
AQUAPORIN_PF_M_S = (3e-4, 8e-4)  # 0.03-0.08 cm/s
BULK_MODULUS_PA = 60.0
PRESSURE_OFFSET_PA = 40.0
MINIMUM_FRACTION = 0.5
MAXIMUM_FRACTION = 2.0


def hydraulic_permeability(pf_m_s, temperature_K):
    """Lp (m/(Pa s)) of an osmotic permeability Pf (m/s): Pf Vw / (R T)."""
    return pf_m_s * MOLAR_VOLUME_WATER_M3_MOL / (GAS_CONSTANT * temperature_K)


def with_water(
    raw,
    *,
    pf_m_s=NO_AQUAPORIN_PF_M_S,
    bulk_modulus_Pa=BULK_MODULUS_PA,
    pressure_offset_Pa=PRESSURE_OFFSET_PA,
    minimum_fraction=MINIMUM_FRACTION,
    maximum_fraction=MAXIMUM_FRACTION,
    impermeant_fmol=0.0,
    availability=1.0,
    bath_pressure_Pa=0.0,
):
    """A resolved_pump_water@1 definition of a resolved_pump_tissue@3 definition."""
    raw = copy.deepcopy(raw)
    m, e = raw["model"], raw["experiment"]
    if m["id"] != "resolved_pump_tissue@3":
        raise ValueError("with_water() takes a resolved_pump_tissue@3 definition")
    m["id"] = "resolved_pump_water@1"
    lp = hydraulic_permeability(pf_m_s, m["temperature_K"])
    finite = [c for c in m["extracellular"] if not c.get("reservoir", False)]
    m["water"] = dict(
        law="ideal_osmosis_linear_compliance_water@1",
        compartments=[
            dict(
                compartment_id=c["id"],
                reference_volume_pL=c["volume_pL"],
                minimum_volume_pL=minimum_fraction * c["volume_pL"],
                maximum_volume_pL=maximum_fraction * c["volume_pL"],
                impermeant_amount_fmol=impermeant_fmol,
                bulk_modulus_Pa=bulk_modulus_Pa,
                pressure_offset_Pa=pressure_offset_Pa,
            )
            for c in (*m["cells"], *finite)
        ],
        baths=[
            dict(compartment_id=c["id"], hydrostatic_pressure_Pa=bath_pressure_Pa)
            for c in m["extracellular"]
            if c.get("reservoir", False)
        ],
        membranes=[
            dict(membrane_id=p["id"], hydraulic_permeability_m_per_Pa_s=lp) for p in m["membranes"]
        ],
    )
    schedule = (
        [dict(time=0.0, availability=float(availability))]
        if not isinstance(availability, (list, tuple))
        else [dict(time=float(t), availability=float(a)) for t, a in availability]
    )
    e["water_controls"] = [
        dict(membrane_id=p["id"], schedule=copy.deepcopy(schedule)) for p in m["membranes"]
    ]
    return raw


SYMPORT_REFERENCE_DIFFERENCE_mM2 = 140 * 95 - 5 * 140  # Lew et al. 1991 reference state


def symport_capacity(flux_mmol_L_h, volume_pL):
    """k (fmol/(s mM^2)) giving flux_mmol_L_h (mmol/(L cells h)) of K:anion efflux at the
    Lew et al. 1991 reference product difference with the volume factor at 1."""
    return flux_mmol_L_h * volume_pL / 3600.0 / SYMPORT_REFERENCE_DIFFERENCE_mM2


def with_symport(raw, *, flux_mmol_L_h=15.0, steepness=1.0, availability=1.0, membranes=None):
    """A resolved_pump_water@2 definition of a resolved_pump_water@1 definition.

    One KCC-type route (k_anion_symport_mass_action@1, roles K and M) on each
    listed membrane (default all), capacity from a red-cell flux per cell volume
    (default 15 mmol/(L cells h), Lew et al. 1991), set volume the cell's water
    reference volume, the given steepness (1: Lew 1991; 0.12: Kaji 1986, derived).
    membranes=[] declares no route.
    """
    raw = copy.deepcopy(raw)
    m, e = raw["model"], raw["experiment"]
    if m["id"] != "resolved_pump_water@1":
        raise ValueError("with_symport() takes a resolved_pump_water@1 definition")
    m["id"] = "resolved_pump_water@2"
    cells = {c["id"]: c for c in m["cells"]}
    reference = {c["compartment_id"]: c["reference_volume_pL"] for c in m["water"]["compartments"]}
    chosen = [p for p in m["membranes"] if membranes is None or p["id"] in membranes]
    m["symport"] = dict(
        law="k_anion_symport_mass_action@1",
        volume_factor="exponential_volume_activation@1",
        roles=dict(potassium="K", anion="M"),
        routes=[
            dict(
                membrane_id=p["id"],
                capacity_fmol_s_mM2=symport_capacity(
                    flux_mmol_L_h, cells[p["inside"]]["volume_pL"]
                ),
                set_volume_pL=reference[p["inside"]],
                steepness=steepness,
            )
            for p in chosen
        ],
    )
    schedule = (
        [dict(time=0.0, availability=float(availability))]
        if not isinstance(availability, (list, tuple))
        else [dict(time=float(t), availability=float(a)) for t, a in availability]
    )
    e["symport_controls"] = [
        dict(membrane_id=p["id"], schedule=copy.deepcopy(schedule)) for p in chosen
    ]
    return raw


def scheduled(raw, *, channel_change=(0.4, 0.5), pump_change=(0.6, 0.8)):
    """A @3 definition with a NaV1.2 availability change and a Na/K pump change.

    Every NaV1.2 population steps to channel_change[1] at channel_change[0] (s)
    and every pump to pump_change[1] at pump_change[0]: one scheduled change of
    each kind inside the run (the equivalence runs' event coverage).
    """
    raw = copy.deepcopy(raw)
    m, e = raw["model"], raw["experiment"]
    nav = {c["id"] for c in m["channels"] if c["kinetic_law"].startswith("nav1p2")}
    for group in e["channel_controls"]:
        if group["channel_id"] in nav:
            held = group["schedule"][0]["availability"]
            group["schedule"] = [
                dict(time=0.0, availability=held),
                dict(time=channel_change[0], availability=channel_change[1]),
            ]
    for group in e["pump_controls"]:
        held = group["schedule"][0]["availability"]
        group["schedule"] = [
            dict(time=0.0, availability=held),
            dict(time=pump_change[0], availability=pump_change[1]),
        ]
    return raw


def heredity_cell(state="H", *, dt=1e-3, end_time=1.0, observation_times=None, solver=None):
    """One heredity cell facing its held bath (surface_pump_v3_fixtures.heredity_cells)."""
    from validation.tissue import surface_pump_v3_fixtures as fixtures

    kind = fixtures.HEREDITY_STATES[state]
    return fixtures.heredity_cells(
        [kind[:4]],
        dt=dt,
        end_time=end_time,
        observation_times=observation_times,
        **({} if solver is None else dict(solver=solver)),
    )


def gated_sheet(*, dt=1e-3, end_time=1.0, solver=None):
    """Seven heredity cells (hexagon of radius 1, each with its held bath) joined by the
    E07-v1 voltage-gated junctions; the centre cell starts in D, the ring in H."""
    from validation.stationary import worlds
    from validation.tissue import surface_pump_v3_fixtures as fixtures

    cells, edges = worlds.hexagon(1)
    states = [fixtures.HEREDITY_STATES["D" if worlds.ring(c) == 0 else "H"][:4] for c in cells]
    raw = worlds.e07_sheet_definition(states, edges, dt=dt, end_time=end_time)
    if solver is not None:
        raw["execution"]["solver"] = solver
    return raw


def scale_world(*, dt=1e-3, end_time=0.01, solver=None):
    """The 825-node W225 world as @3 with NaV1.2 and Kir2.1 on every patch."""
    from validation.tissue import surface_pump_v3_study as study

    raw = study.tissue_definition(dt=dt, end_time=end_time)
    if solver is not None:
        raw["execution"]["solver"] = solver
    return raw
