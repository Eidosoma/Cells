"""FR-3's acceptance worlds: cells.operator.site_occupancy@1 in the references' registered worlds (FR-3, D216).

The worlds are the references' own: validation/fr3/references/reference_inputs.json, registered
code-blind before any engine output (the lead's ruling of 17 November 2026: the references design
and register FR-3's worlds, and the FR lane builds its protocol on them, through paths). This
module is the engine-layout adapter. It builds each world as an engine definition from its
physical description, on secreted_species_fixtures' quiescent worlds (passive cells, zero ion
permeability on every patch, every node at the bath's ion composition with a zero charge anchor)
with site_occupancy_fixtures' `population` and `with_site_occupancy`. It reads the references'
inputs file only; it imports nothing from the references.

The layout, from the physical description (reference_inputs.json's conventions):
* every `cell` node is a cell of its declared volume, with its wall patch on the held bath `bath`
  (zero permeability: the electrical gauge only; the ligand is impermeant and no face exists, so
  nothing crosses it); every `finite_outside` node is a finite extracellular node;
* every outward population of a cell facing a node sits on that cell's contact patch to the node,
  `contact_<cell>_<node>` (one patch per cell and node: the only link between them, so the world
  is face-free); every inward population of a cell sits on its wall patch, facing inside (it binds
  from the cytosol; its patch carries no other role in a face-free world);
* the ligand L is the engine's neutral species S (D150's), declared at every node at its listed
  concentration, the trace included, and at the world's trace in the held bath; the world's
  `trace_mM` is the ligand's declared trace (cells.operator.site_occupancy@1's form (a), §4.3);
* `site_controls` epochs become one schedule per population and route. A population without an
  internalisation route gets no internalisation schedule (the engine refuses a schedule for an
  undeclared route; the inputs list a multiplier for it, which no law reads);
* the record times become observation times on the step grid (k dt, k = round(t / dt)).

Control worlds (each one declared change of a registered world, run by the engine, judged by how
far it departs from the registered world's reference): `rates` (every k_on, k_off or k_int x
1.01), `alpha_ignored` (accessible_fraction 1), `binding_multiplier` (the schedule ignored or
squared), `internalisation_multiplier_ignored`, `cell_volume` (a cell's volume replaced, its
concentrations kept), and Q4's `kinetic_factor` (K: alpha 1 and the binding multiplier at alpha,
both directions x alpha, §2.3) and `affinity_factor` (A: alpha 1 and k_on x alpha).
"""

import copy
import json
import math
from pathlib import Path

from cells.operators.site_occupancy import SITES_PER_FMOL
from validation.tissue import secreted_species_fixtures as fx
from validation.tissue import site_occupancy_fixtures as sfx

ROOT = Path(__file__).resolve().parents[2]
INPUTS = ROOT / "validation" / "fr3" / "references" / "reference_inputs.json"
DESIGN = ROOT / "validation" / "fr3" / "references" / "designs" / "fr3_reference_design.json"
SOLVER = fx.IMEX
DECLARED_DT = 1e-3
LADDER_S = (1e-3, 5e-4, 2.5e-4)  # The references' dt_ladder_s (checked against the file).
LADDER_WORLD = "q1_fast"  # The lead's ruling: the orders on q1_fast.
LIGAND = sfx.LIGAND  # The engine's S stands for the references' L.
TEMPERATURE_K = 310.0  # fx.world's.
RECORD_UNIT_S = 1e-3  # Records are aligned on integer milliseconds.


def inputs():
    return json.loads(INPUTS.read_text())


def world_ids():
    return list(inputs()["worlds"])


def registered(world_id):
    """The references' world, as registered (a deep copy)."""
    return copy.deepcopy(inputs()["worlds"][world_id])


def patch_of(population):
    """(patch id, face) of a population in the engine's layout (module docstring)."""
    owner = population["owner"]
    if owner["orientation"] == "outward":
        return f"contact_{owner['cell']}_{owner['faces_node']}", "outside"
    if owner["orientation"] == "inward":
        if owner["faces_node"] != owner["cell"]:
            raise ValueError(f"an inward population faces its own cell: {population['id']}")
        return f"wall_{owner['cell']}", "inside"
    raise ValueError(f"unknown orientation {owner['orientation']!r}")


def record_times(world, dt):
    """The world's record times on the step grid: k dt, k = round(t / dt), strictly increasing."""
    steps = sorted({round(t / dt) for t in world["record_times_s"]})
    return [k * dt for k in steps]


def _schedules(world, populations):
    """{(population, route): [(time, multiplier), ...]} from the world's epochs."""
    internalising = {p["id"] for p in populations if p["internalisation"] is not None}
    out = {}
    for epoch in world["site_controls"]:
        t = float(epoch["time_s"])
        for pid, m in epoch.get("binding", {}).items():
            out.setdefault((pid, "binding"), []).append((t, float(m)))
        for pid, m in epoch.get("internalisation", {}).items():
            if pid in internalising:
                out.setdefault((pid, "internalisation"), []).append((t, float(m)))
    return out


def build(world, *, dt=DECLARED_DT, solver=SOLVER, operator=True, populations=True):
    """The engine definition of a world in the references' form (registered or a control's);
    operator=False: the same world without the operator's block (Q6_idle's reference);
    populations=False: the operator declared with no populations, the layout kept."""
    if float(world.get("temperature_K", TEMPERATURE_K)) != TEMPERATURE_K:
        raise ValueError("the adapter's worlds are at 310 K (fx.world's temperature)")
    nodes = world["nodes"]
    cells = tuple((nid, float(n["volume_pL"])) for nid, n in nodes.items() if n["kind"] == "cell")
    finite = tuple(
        (nid, float(n["volume_pL"])) for nid, n in nodes.items() if n["kind"] == "finite_outside"
    )
    if len(cells) + len(finite) != len(nodes):
        raise ValueError("every node is a cell or a finite outside node")
    contacts, declared = [], []
    for p in world["populations"]:
        patch, face = patch_of(p)
        owner = p["owner"]
        if face == "outside" and (patch, owner["cell"], owner["faces_node"]) not in contacts:
            contacts.append((patch, owner["cell"], owner["faces_node"]))
        k_int = None if p["internalisation"] is None else p["internalisation"]["rate_per_s"]
        destination = None if p["internalisation"] is None else p["internalisation"]["destination"]
        declared.append(
            sfx.population(
                p["id"],
                patch=patch,
                face=face,
                copies=p["copies"],
                sites_per_copy=p["sites_per_copy"],
                alpha=p["accessible_fraction"],
                k_on=p["association_rate_per_mM_per_s"],
                k_off=p["dissociation_rate_per_s"],
                theta0=p["initial_occupancy"],
                k_int=k_int,
                destination=destination or "cell",
            )
        )
    end = float(world["end_s"])
    trace = float(world["trace_mM"])
    raw = fx.world(
        cells=cells,
        nodes=finite,
        contacts=tuple(contacts),
        faces=(),
        dt=dt,
        end=end,
        solver=solver,
        trace_mM=trace,
        concentrations_mM={nid: float(n["L_mM"]) for nid, n in nodes.items()},
        observation_times=record_times(world, dt),
    )
    if not operator:
        return raw
    if not populations:
        return sfx.with_site_occupancy(raw, [], ligands=[sfx.ligand(trace_mM=trace)], controls={})
    return sfx.with_site_occupancy(
        raw,
        declared,
        ligands=[sfx.ligand(trace_mM=trace)],
        controls=_schedules(world, declared),
    )


def registered_world(world_id, *, dt=DECLARED_DT):
    return build(registered(world_id), dt=dt)


# ------------------------------------------------------------------ control worlds


def rates(world_id, which, factor=1.01):
    """Every population's k_on, k_off or k_int (`which`) x factor."""
    w = registered(world_id)
    key = dict(k_on="association_rate_per_mM_per_s", k_off="dissociation_rate_per_s")
    for p in w["populations"]:
        if which == "k_int":
            if p["internalisation"] is None:
                raise ValueError(f"{world_id}: {p['id']} does not internalise")
            p["internalisation"]["rate_per_s"] *= factor
        else:
            p[key[which]] *= factor
    return w


def alpha_ignored(world_id):
    """Every population's accessible fraction taken as 1."""
    w = registered(world_id)
    for p in w["populations"]:
        p["accessible_fraction"] = 1.0
    return w


def binding_multiplier(world_id, mode):
    """The binding multiplier `ignored` (1 at every epoch) or `squared` (m_b^2 at every epoch)."""
    w = registered(world_id)
    for epoch in w["site_controls"]:
        epoch["binding"] = {
            pid: 1.0 if mode == "ignored" else float(m) ** 2
            for pid, m in epoch["binding"].items()
        }
    return w


def internalisation_multiplier_ignored(world_id):
    """The internalisation multiplier 1 at every epoch."""
    w = registered(world_id)
    for epoch in w["site_controls"]:
        epoch["internalisation"] = {pid: 1.0 for pid in epoch["internalisation"]}
    return w


def cell_volume(world_id, cell, volume_pL):
    """A cell's volume replaced (the receiving cell's volume dropped), its concentration kept."""
    w = registered(world_id)
    w["nodes"][cell]["volume_pL"] = float(volume_pL)
    return w


def kinetic_factor(world_id, alpha):
    """(K), §2.3: alpha 1, and both binding directions x alpha (the binding multiplier at alpha
    at every epoch): the equilibrium unchanged, the approach alpha times slower."""
    w = registered(world_id)
    for p in w["populations"]:
        p["accessible_fraction"] = 1.0
    for epoch in w["site_controls"]:
        epoch["binding"] = {pid: float(m) * alpha for pid, m in epoch["binding"].items()}
    return w


def affinity_factor(world_id, alpha):
    """(A), §2.3: alpha 1, and k_on x alpha (K_d / alpha): every site fills at saturation."""
    w = registered(world_id)
    for p in w["populations"]:
        p["accessible_fraction"] = 1.0
        p["association_rate_per_mM_per_s"] *= alpha
    return w


def sites_fmol(world):
    """[population] S = alpha nu N / N_f (fmol), the declared capacities (N_f exact, SI 2019)."""
    return [
        p["accessible_fraction"] * p["sites_per_copy"] * p["copies"] / SITES_PER_FMOL
        for p in world["populations"]
    ]


def world_sites_fmol(world):
    """S_world = sum_k S_k (fmol): the scale of the state budget (declared)."""
    return math.fsum(sites_fmol(world))
