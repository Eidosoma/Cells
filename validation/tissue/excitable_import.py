"""Track E M1: a conduction assay started from a slow world's saved state (D153 rule (b); D170).

The assay is a new run of a definition whose initial values are imported. It records the source
checkpoint's manifest digest and identities, claims no continuity, and is judged on its own
(EXCITABLE_TISSUE_DESIGN.md section 4.5). v1 takes one world's complete numerical checkpoint of
cells.model.resolved_pump_tissue@3 (`world-N/manifest.json` and `state.npz`, as the engine writes them).

What it carries (D170 ruling 5):
- every cell's and extracellular compartment's amounts at the checkpoint (reference plus
  increment), with the charge that follows from them and the source's fixed background,
  q = F (sum z a + fixed);
- every channel population's gates;
- every junction's **effective availability, frozen at the import time**: the source's schedule
  value at that time times its junction gate, with the gate pinned open in the assay (its
  BETSE-type relaxation takes seconds, against an assay of 50-200 ms). Each junction's carriage
  is recorded: schedule value, gate, effective availability and its source;
- the source's membrane, pump and channel availabilities at the import time, frozen.

What it refuses, at definition time:
- any source other than one world of cells.model.resolved_pump_tissue@3. Composites, Track R's among them,
  wait for their carriage (the formation factor's effective availability), which D170 ruling 5
  names but whose state this v1 does not read;
- water: a model with water, or cell volumes that differ from the definition's ("until the
  assay's identity takes water");
- any junction below the floor s * r_gj >= 20, closed ones and gate-reduced ones included. The
  coupling is each junction's permeability and area against the E07-v1 junction's (s = 1) times
  its effective availability; the smallest species ratio is used.

The driver rule: excitable runs book junction heat with cells.heat.trapezoid_nonnegative@1 (design note
section 4.4; the run-time dissipation refusal backs it). `require_trapezoid` enforces it.

`rest_check` executes the engine: the unstimulated imported state at the assay's own step for
the protocol's length must stay within a declared band of its imported voltages; an import that
drifts or fires is refused before any stimulus runs.
"""

import copy
import hashlib
import json
import math
from pathlib import Path

import numpy as np

from cells.laws.electrochemistry import CHARGE_PER_FMOL
from validation.stationary import worlds
from validation.tissue import field_solver_choice

SOURCE_MODEL = "cells.model.resolved_pump_tissue@3"
CHECKPOINT_KIND = "cells_complete_numerical_checkpoint"
TRAPEZOID = "cells.heat.trapezoid_nonnegative@1"
JUNCTION_GATE_LAW = "cells.junction.junction_voltage_relaxation@1"
FLOOR = 20.0
VOLUME_RTOL = 1e-12
REST_BAND_V = 1e-3
CONTROL_GROUPS = (
    ("membrane_controls", "membrane_id"),
    ("pump_controls", "pump_id"),
    ("calcium_pump_controls", "pump_id"),
    ("channel_controls", "channel_id"),
)


class ImportRefused(ValueError):
    """The source cannot be carried into a conduction assay (the message names why)."""


def start_state(folder):
    """One world's checkpoint: (state, manifest, the manifest file's sha256). No execution."""
    folder = Path(folder)
    raw_manifest = (folder / "manifest.json").read_bytes()
    manifest = json.loads(raw_manifest)
    state = dict(np.load(folder / "state.npz"))
    return state, manifest, hashlib.sha256(raw_manifest).hexdigest()


def value_at(schedule, time_s):
    """A piecewise-constant schedule's availability at a time (the last entry at or before it)."""
    rows = sorted(schedule, key=lambda r: r["time"])
    current = rows[0]["availability"]
    for row in rows:
        if row["time"] <= time_s:
            current = row["availability"]
    return float(current)


def coupling_ratio(junction):
    """A junction's permeability-times-area against the E07-v1 junction's (s = 1): the smallest
    species ratio over the species the E07 junction carries."""
    base = worlds.e07_junction()
    ratios = [
        junction["permeability_m_per_s"].get(sp, 0.0) * junction["area_m2"] / (p * base["area_m2"])
        for sp, p in base["permeability_m_per_s"].items()
        if p > 0
    ]
    return min(ratios)


def require_trapezoid(raw):
    """The driver rule: an excitable definition with junctions books their heat by trapezoid."""
    m = raw["model"]
    if m.get("junctions") and m.get("junction_heat_booking") != TRAPEZOID:
        raise ImportRefused(
            f"junction heat must be booked with {TRAPEZOID} in excitable runs (design note "
            f"section 4.4), not {m.get('junction_heat_booking', 'the default explicit_tableau')}"
        )
    return raw


def refuse_unsupported(manifest, state):
    if manifest.get("kind") != CHECKPOINT_KIND:
        raise ImportRefused(f"one world's {CHECKPOINT_KIND} is needed, not {manifest.get('kind')}")
    model = manifest["spec"]["model"]
    if model.get("id") != SOURCE_MODEL:
        raise ImportRefused(
            f"v1 imports {SOURCE_MODEL} only, not {model.get('id')}: a composite's carriage (the "
            "formation factor's effective availability, D170 ruling 5) is not read by v1"
        )
    if "water" in json.dumps(model.get("id", "")) or "water" in str(model.get("water", "")):
        raise ImportRefused("water's volumes are refused until the assay's identity takes water")
    declared = np.asarray([c["volume_pL"] for c in model["cells"]], dtype=float)
    held = np.asarray(state["volume"], dtype=float)[: len(declared)]
    if np.any(np.abs(held - declared) > VOLUME_RTOL * np.abs(declared)):
        raise ImportRefused(
            "cell volumes differ from the definition's: water's volumes are refused until the "
            "assay's identity takes water"
        )


def carry_amounts(rows, reference, increment, species, valence):
    """Set each row's amounts at the checkpoint and the charge that follows (in place)."""
    for i, row in enumerate(rows):
        amount = reference[:, i] + increment[:, i]
        row["initial_amount_fmol"] = {s: float(amount[k]) for k, s in enumerate(species)}
        ionic = math.fsum(float(valence[k]) * float(amount[k]) for k in range(len(species)))
        row["initial_charge_C"] = CHARGE_PER_FMOL * (ionic + row["fixed_charge_equivalent_fmol"])


def assay_definition(
    folder,
    *,
    dt,
    end_time,
    observation_times=None,
    stimulus=None,
    floor=FLOOR,
    solver=None,
):
    """The assay's raw definition and its rule (b) record (see the module docstring).

    stimulus: None, or dict(cells=[cell indices], window=(t_on, t_off), m_s=permeability), added
    as K and Na leak populations on those cells (the probe's stimulus), on only in the window.
    """
    state, manifest, digest = start_state(folder)
    refuse_unsupported(manifest, state)
    raw = copy.deepcopy(manifest["spec"])
    m, e, x = raw["model"], raw["experiment"], raw["execution"]
    t_import = float(manifest["clock"]["time"])
    species = [s["id"] for s in m["species"]]
    valence = [s["valence"] for s in m["species"]]
    if list(np.asarray(state["valence"]).ravel()) != [float(v) for v in valence]:
        raise ImportRefused("the state's species order differs from the definition's")
    carry_amounts(
        m["cells"], state["amount_reference"], state["amount_increment"], species, valence
    )
    carry_amounts(
        m["extracellular"],
        state["extracellular_amount_reference"],
        state["extracellular_amount_increment"],
        species,
        valence,
    )
    gates = np.asarray(state["channel_gate"])
    for k, c in enumerate(m["channels"]):
        c["initial_gate"] = [float(g) for g in gates[: len(c["initial_gate"]), k]]
    # Membrane, pump and channel availabilities at the import time, frozen.
    frozen = {}
    for group, key in CONTROL_GROUPS:
        for row in e.get(group, []):
            v = value_at(row["schedule"], t_import)
            row["schedule"] = [dict(time=0.0, availability=v)]
            frozen[f"{group}:{row[key]}"] = v
    # Junctions: the effective availability frozen, the gate pinned open, the floor checked.
    controls = {row["junction_id"]: row for row in e.get("junction_controls", [])}
    jgate = np.asarray(state["junction_gate"])
    carriage, below = [], []
    for k, j in enumerate(m["junctions"]):
        row = controls.get(j["id"])
        scheduled = 1.0 if row is None else value_at(row["schedule"], t_import)
        gate = float(jgate[k]) if j.get("gate", {}).get("law") == JUNCTION_GATE_LAW else 1.0
        effective = scheduled * gate
        ratio = coupling_ratio(j)
        coupling = ratio * effective
        carriage.append(
            dict(
                junction=j["id"],
                scheduled_availability=scheduled,
                gate=gate,
                effective_availability=effective,
                source="schedule x junction gate at the import time",
                coupling_ratio_to_e07=ratio,
                s_times_r_gj=coupling,
            )
        )
        if coupling < floor:
            below.append((j["id"], coupling))
        j["gate"] = dict(
            law=JUNCTION_GATE_LAW,
            threshold_voltage_V=0.0,
            minimum_open_fraction=1.0,
            initial_gate=1.0,
        )
        if row is None:
            row = dict(junction_id=j["id"])
            e.setdefault("junction_controls", []).append(row)
        row["schedule"] = [dict(time=0.0, availability=effective)]
    if below:
        raise ImportRefused(
            f"{len(below)} junction(s) below the floor s * r_gj >= {floor:g} (closed and "
            f"gate-reduced ones included), for example {below[:3]}"
        )
    if stimulus is not None:
        add_stimulus(raw, stimulus)
    m["junction_heat_booking"] = TRAPEZOID
    e["end_time"] = float(end_time)
    e["observation_times"] = list(observation_times or [0.0, float(end_time)])
    x["dt"] = float(dt)
    x["max_steps"] = int(math.ceil(end_time / dt)) + 16
    x["channel_capacity"] = max(x.get("channel_capacity", 0), len(m["channels"]))
    if solver is not None:
        x["solver"] = solver
    raw = field_solver_choice.declare(require_trapezoid(raw))
    record = dict(
        kind="track_e_imported_start@1",
        rule="D153 rule (b): a new run of a definition whose initial values are imported; it "
        "claims no continuity and is judged on its own",
        source=dict(
            folder=str(Path(folder).resolve()),
            manifest_file_sha256=digest,
            manifest_sha256=manifest.get("manifest_sha256"),
            spec_sha256=manifest.get("spec_sha256"),
            state_sha256=manifest.get("state_sha256"),
            clock=manifest.get("clock"),
            runtime=manifest.get("runtime"),
            model=manifest["spec"]["model"]["id"],
            dt_s=manifest["spec"]["execution"]["dt"],
        ),
        import_time_s=t_import,
        floor=floor,
        junction_carriage=carriage,
        frozen_availabilities=frozen,
        assay=dict(
            dt_s=float(dt),
            end_time_s=float(end_time),
            booking=TRAPEZOID,
            field_solver=raw["execution"]["field_solver"],
            free_field_offsets=field_solver_choice.free_field_offsets(raw),
        ),  # fmt: skip
    )
    return raw, record


def add_stimulus(raw, stimulus):
    """K and Na leak populations of permeability m_s on the cells, on in the window (in place)."""
    from cells.definitions.surface_pump_v3_spec import KLEAK_LAW_ID, NALEAK_LAW_ID

    m, e = raw["model"], raw["experiment"]
    on, off = stimulus["window"]
    schedule = [
        dict(time=0.0, availability=0.0),
        dict(time=float(on), availability=1.0),
        dict(time=float(off), availability=0.0),
    ]
    first = {}  # Each cell's first membrane carries its stimulus (a cell may have several).
    for mb in m.get("membranes", []):
        first.setdefault(mb["inside"], mb["id"])
    for i in stimulus["cells"]:
        cell = m["cells"][i]["id"]
        if cell not in first:
            raise ImportRefused(f"{cell} has no membrane for a stimulus")
        membrane = first[cell]
        for name, law, ion in (("stimk", KLEAK_LAW_ID, "K"), ("stimna", NALEAK_LAW_ID, "Na")):
            cid = f"{name}_{i}"
            m["channels"].append(
                dict(
                    id=cid,
                    membrane_id=membrane,
                    kinetic_law=law,
                    max_permeability_m_per_s=float(stimulus["m_s"]),
                    abundance=1.0,
                    initial_gate=[],
                    permeant_ions=[dict(species_id=ion, relative_permeability=1.0)],
                )
            )
            e["channel_controls"].append(dict(channel_id=cid, schedule=copy.deepcopy(schedule)))


def rest_check(raw, *, band_V=REST_BAND_V, execute=None):
    """Executes the engine: the unstimulated assay must stay within band_V of its imported Vm.

    execute: the runner returning dict(times, vm, refusal) (default: excitable_sheet's).
    Returns a dict with passes, the largest drift and the cells outside the band.
    """
    if execute is None:
        from validation.tissue.excitable_sheet import execute_sheet as execute
    for row in raw["experiment"]["channel_controls"]:
        if row["channel_id"].startswith(("stimk_", "stimna_")):
            raise ImportRefused("rest_check runs the unstimulated assay: remove the stimulus")
    run = execute(raw)
    if run["refusal"] is not None or len(run["times"]) < 2:
        return dict(passes=False, refusal=run["refusal"], largest_drift_V=None, outside=[])
    vm = np.asarray(run["vm"])
    drift = np.abs(vm - vm[0])
    outside = [int(i) for i in np.flatnonzero(drift.max(axis=0) > band_V)]
    return dict(
        passes=not outside,
        refusal=None,
        largest_drift_V=float(drift.max()),
        band_V=band_V,
        outside=outside,
        length_s=float(run["times"][-1] - run["times"][0]),
    )
