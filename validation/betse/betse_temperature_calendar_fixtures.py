"""Declared fixed-state temperature/calendar microcases; no numerical imports."""

from copy import deepcopy

from validation.betse.betse_fast_solver_fixtures import fixture as material_fixture

CASES = ("fresh", "carried", "reordered", "divalent", "zero_voltage", "empty_program")
PROFILES = {
    "literal_native": dict(R_J_mol_K=8.314, F_C_mol=96485.0, q_C=1.602e-19, kb_J_K=1.3806e-23),
    "matched_SI": dict(
        R_J_mol_K=6.02214076e23 * 1.380649e-23,
        F_C_mol=6.02214076e23 * 1.602176634e-19,
        q_C=1.602176634e-19,
        kb_J_K=1.380649e-23,
    ),
}


def fixture(case="fresh", phase="SIM", profile="literal_native", count=7):
    if case not in CASES or phase not in ("INIT", "SIM") or profile not in PROFILES:
        raise ValueError("Require an explicit manufactured temperature/calendar case")
    base = material_fixture(case if case in ("reordered", "divalent") else "no_ecm", phase)
    material = deepcopy(base["definition"])
    material["parameters"].update(PROFILES[profile])
    material["parameters"].update(
        configured_temperature_K=298.15,
        temperature_K=285.0 if case == "carried" else 298.15,
    )
    owners = material["geometry"]["membrane_ids"]
    m = len(owners)
    gates = dict(
        owner_ids=owners[:],
        initial_hh_m=[0.2 + 0.01 * j for j in range(m)],
        initial_hh_h=[0.7 - 0.01 * j for j in range(m)],
        initial_ml_m=[0.3 + 0.02 * j for j in range(m)],
        hh_m_inf=[0.6 - 0.01 * j for j in range(m)],
        hh_h_inf=[0.3 + 0.01 * j for j in range(m)],
        ml_m_inf=[0.5 + 0.02 * j for j in range(m)],
        hh_m_tau_native=[3.0 + 0.2 * j for j in range(m)],
        hh_h_tau_native=[7.0 + 0.3 * j for j in range(m)],
        ml_tau_native=[5.0 + 0.1 * j for j in range(m)],
        time_unit=1000.0,
        Phi=0.7,
    )
    raw = dict(
        kind="cells.betse_temperature_calendar_inputs@1",
        provenance="Explicit held material/cache and HH/ML source-clock probes; no coupled solver",
        constant_profile=profile,
        entry_mode="explicit_carried_runtime" if case == "carried" else "fresh_configured_copy",
        material=material,
        clock_probes=gates,
        membrane_voltage_V=[0.0 if case == "zero_voltage" else -0.05 + j * 0.003 for j in range(m)],
        junction_voltage_V=[0.0 if case == "zero_voltage" else -0.01 + j * 0.001 for j in range(m)],
    )
    calendar = dict(
        phase=phase,
        step_count=count,
        dt_s=0.1,
        sample_stride=2.5,
        requested_duration_s=None,
        provenance="Explicit original source calendar with distinct label spacing and physical dt",
    )
    events = (
        []
        if case == "empty_program"
        else [
            dict(
                kind="temperature",
                on_s=0.15,
                off_s=0.55,
                change_s=0.12,
                amplitude=0.08,
                target_ids=[],
                positive_boundary=None,
                negative_boundary=None,
            )
        ]
    )
    return dict(raw=raw, calendar=calendar, events=events)
