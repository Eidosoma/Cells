"""Small worlds for scheduled_bath_composition@1 (FR-10, docs/BATH_SCHEDULE_DESIGN.md).

All values are synthetic. The worlds are secreted_species_fixtures' quiescent worlds (passive
cells, zero membrane permeability, zero ion diffusivity on every face, every node at the bath's ion
composition), so the energy flows and bounds are the neutral species S's own: the species-only
worlds of D150 §7. The bath schedule is added with its formula units and events.

* dosed_world: the first delivery world's dose leg: cell_0 with its wall patch on the held bath
  `bath`, a contact patch on the finite node ecs_0, which face_0 joins to the bath. S starts from a
  declared profile (resolved by default, the bath at `c0` and the node and cell near it).
* with_bath_schedule: the operator's block and events on any composite definition.
"""

import copy

from validation.tissue import secreted_species_fixtures as fx

LAW = "scheduled_bath_composition@1"
CARGO = {"cargo": {fx.SPECIES: 1}}  # S is neutral: its own formula unit.
SALTS = {"NaCl": {"Na": 1, "Cl": 1}, "KCl": {"K": 1, "Cl": 1}}


def with_bath_schedule(raw, baths, units, events):
    """baths: held bath IDs; units: {name: {species: count}}; events: (time, baths, {unit: mM})
    triples."""
    out = copy.deepcopy(raw)
    out["model"]["operators"].append(
        dict(
            law=LAW,
            baths=list(baths),
            formula_units={k: dict(v) for k, v in units.items()},
        )
    )
    out["experiment"]["bath_composition_events"] = [
        dict(time=t, baths=list(b), formula_units_mM=dict(o)) for t, b, o in events
    ]
    return out


def dosed_world(
    *,
    c0=1e-3,
    profile=None,
    dt=1e-3,
    end=0.05,
    solver=fx.IMEX,
    trace_mM=None,
    observation_times=None,
    face=(1e-10, 1e-5),
):
    """The species-only dose leg (module docstring): the bath at c0, the node and cell resolved
    near it unless `profile` ({node: mM}) says otherwise. A composite definition with no
    operators; add the schedule with with_bath_schedule."""
    concentrations = dict(bath=c0, ecs_0=0.9 * c0, cell_0=0.5 * c0)
    if profile is not None:
        concentrations = dict(profile, bath=profile.get("bath", c0))
    kwargs = {} if trace_mM is None else dict(trace_mM=trace_mM)
    return fx.world(
        cells=(("cell_0", 1.0),),
        nodes=(("ecs_0", 1.0),),
        baths=("bath",),
        contacts=(("contact_0", "cell_0", "ecs_0"),),
        faces=(("face_0", "ecs_0", "bath", face[0], face[1]),),
        dt=dt,
        end=end,
        observation_times=observation_times or [0.0, end],
        solver=solver,
        concentrations_mM=concentrations,
        **kwargs,
    )
