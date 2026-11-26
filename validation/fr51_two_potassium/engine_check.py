"""FR-51's two-potassium engine check: section 2 of REGISTRATION.md (this folder), as tagged.

**The worlds.** One cell on a held bath, on cells.model.resolved_pump_tissue@3, per arm and external K level.
Its one patch carries two cells.channel.kleak_always_open@1 populations, equal in permeability, abundance and
availability:
- "blocked" carries cells.channel_block.open_channel_block_weighted_modes@1. The block is referenced to the K reversal,
  {"reversal_of": "K"}, in the reversal arm and to the membrane voltage in the absolute arm;
- "free" carries no block: the matched free population.

**The calibration** is the anchor file's: temperature, internal K, free spermine, and the two
modes' weights, midpoints M and effective valences z. K(0) = c_B exp[z (M - E_0)/(1000 R T/F)], with
E_0 the concentration-based K reversal at 5.4 mM in the reversal arm and 0 in the absolute arm. K(0)
is computed once per arm, and held at every level and in every plant.

**The half crossing** is the voltage at which the blocked population's current is half the free
population's: Brent's bracketed root-find on the compiled clamp, jax.jit of the model's
clamped_channel_flux. The bracket is wider than the laws' voltage window, so that a plant's crossing
is found wherever it goes; the clamp has no window.

**Judged, as section 2 says.** The criteria hold each difference to 1e-6 mV, the shifts against the
exact 1000 (R T/F) ln(K_o/5.4). Each plant reruns the whole check with one planted change; it must
fail a criterion (caught) and move as its parenthesis says (as written). If an honest criterion
fails, no plant runs.

**Recorded, not judged.** Where section 2 can be read two ways, the second reading runs as well:
- the matched free population as the unblocked twin world's own population (FR-51's judged form);
- plant 1 with K(0) rebuilt for the membrane voltage (E_0 = 0), where the judged one holds K(0).
  Plant 2's rebuilt K(0) lies below the engine's admitted range, so it has the one reading.
The criteria hold for any two modes, so the 5.4 mM crossing is also set beside the closed form's,
from the midpoints alone, and beside the anchor's reading of the trace.

**Provenance.** The engine is a frozen snapshot, verified with its own tool; every loaded cells
module must come from its src. The registration is read at its tag, and the two files that section 9
pins are hashed at their revision and compared with it. The scorer is only hashed.

Usage (PYTHONPATH is the snapshot's src, JAX_ENABLE_X64=1, JAX_PLATFORMS=cpu):
    python -P engine_check.py --repository CHECKOUT --snapshot SNAPSHOT --out NEW_DIRECTORY
Writes honest.json before any plant runs, then result.json. Exits 0 if section 2 passes, 1 if not.
"""

import argparse
import contextlib
import hashlib
import importlib.util
import json
import math
import os
import platform
import re
import subprocess
import sys
from datetime import UTC, datetime
from functools import partial
from pathlib import Path

import jax
import jax.numpy as jnp
import numpy as np
import scipy
from scipy.optimize import brentq

from cells.definitions.specs import parse_spec
from cells.definitions.surface_pump_v3_spec import control_values
from cells.laws import electrochemistry
from cells.laws.channels import open_channel_block as block_law
from cells.models.surface_pump_v3 import VOLTAGE_DOMAIN_V
from cells.registry.models import get_model

TAG = "fr51-two-potassium-registered-2026-11-25"
REGISTRATION = "validation/fr51_two_potassium/REGISTRATION.md"
MODEL, POPULATION = "cells.model.resolved_pump_tissue@3", "cells.channel.kleak_always_open@1"

REFERENCE = {"reversal": {"reversal_of": "K"}, "absolute": "membrane_voltage"}
LEVELS_mM = (5.4, 10.0, 20.0)
BASE_mM, SHIFTED_mM = LEVELS_mM[0], LEVELS_mM[1:]
TOLERANCE_mV = 1e-6
HALF = 0.5
BRACKET_V = (-0.3, 0.3)
PLANTED_EXTERNAL_mM, PLANTED_INTERNAL_mM = 11.0, 150.0  # For 10 mM and for 145 mM.

BOLTZMANN_J_PER_K, ELEMENTARY_CHARGE_C = 1.380649e-23, 1.602176634e-19  # The SI's, exact.

# What the ratio does not read: the geometry, the population's size and the other species.
VOLUME_pL, AREA_m2, CAPACITANCE_F_PER_m2, PERMEABILITY_M_PER_S = 1.0, 1e-9, 0.01, 1e-8
INSIDE_mM, OUTSIDE_mM = {"Na": 10.0, "Cl": 20.0}, {"Na": 145.0, "Cl": 120.0}
VALENCE = {"Na": 1, "K": 1, "Cl": -1}
# Spermine, inside. With effective valences declared, the engine reads the valence's sign alone.
BLOCKER = {"id": "spermine", "valence": 4, "side": "inside"}


# --- The calibration and its K(0) rule -----------------------------------------------------------


def thermal_mV(temperature_K):
    """1000 R T/F (mV)."""
    return 1000.0 * BOLTZMANN_J_PER_K * temperature_K / ELEMENTARY_CHARGE_C


def read_calibration(anchor):
    """The anchor file's calibration. The one fitted weight is mode 1's; mode 2 has the rest."""
    weight, mid1, mid2, z1, z2 = anchor["calibration"]["fit_parameters_weight_mid1_mid2_z1_z2"]
    out = dict(
        temperature_K=anchor["temperature_K"],
        internal_K_mM=anchor["internal_K_mM"],
        external_K_mM=anchor["calibration"]["fit_external_K_mM"],
        spermine_mM=anchor["estimated_free_spermine_mM"],
        modes=[
            dict(weight=weight, midpoint_mV=mid1, valence=z1),
            dict(weight=1.0 - weight, midpoint_mV=mid2, valence=z2),
        ],
    )
    if out["external_K_mM"] != BASE_mM:
        raise ValueError("The anchor is not calibrated at the registered base level")
    return out


def k0_mM(calibration, e0_mV):
    """Each mode's K(0) = c_B exp[z (M - E_0)/(1000 R T/F)] (mM)."""
    thermal = thermal_mV(calibration["temperature_K"])
    return [
        calibration["spermine_mM"] * math.exp(m["valence"] * (m["midpoint_mV"] - e0_mV) / thermal)
        for m in calibration["modes"]
    ]


# --- The worlds ----------------------------------------------------------------------------------


def definition(world, *, blocked=True):
    """The raw definition of a world: {calibration, reference, k0_mM, external_K_mM,
    internal_K_mM}. Without its block it is the unblocked twin."""
    calibration = world["calibration"]
    inside = INSIDE_mM | {"K": world["internal_K_mM"]}
    outside = OUTSIDE_mM | {"K": world["external_K_mM"]}

    def node(name, concentration):
        amounts = {s: concentration[s] * VOLUME_pL for s in VALENCE}
        return dict(
            id=name,
            volume_pL=VOLUME_pL,
            initial_amount_fmol=amounts,
            fixed_charge_equivalent_fmol=-math.fsum(VALENCE[s] * amounts[s] for s in VALENCE),
            initial_charge_C=0.0,
        )

    def population(name):
        return dict(
            id=name,
            membrane_id="patch",
            kinetic_law=POPULATION,
            max_permeability_m_per_s=PERMEABILITY_M_PER_S,
            abundance=1.0,
            initial_gate=[],
            permeant_ions=[dict(species_id="K", relative_permeability=1.0)],
        )

    channels = [population("blocked"), population("free")]
    if blocked:
        channels[0]["block"] = dict(
            law=block_law.LAW_ID,
            blocker=BLOCKER | {"concentration_mM": calibration["spermine_mM"]},
            reference=world["reference"],
            modes=[
                dict(weight=m["weight"], k0_mM=k0, effective_valence=m["valence"])
                for m, k0 in zip(calibration["modes"], world["k0_mM"], strict=True)
            ],
        )
    always = [dict(time=0.0, availability=1.0)]
    return dict(
        schema_version=1,
        model=dict(
            id=MODEL,
            temperature_K=calibration["temperature_K"],
            species=[dict(id=s, valence=z) for s, z in VALENCE.items()],
            cells=[node("cell", inside)],
            extracellular=[node("bath", outside) | dict(reservoir=True, boundary_potential_V=0.0)],
            membranes=[
                dict(
                    id="patch",
                    inside="cell",
                    outside="bath",
                    area_m2=AREA_m2,
                    capacitance_F=CAPACITANCE_F_PER_m2 * AREA_m2,
                    permeability_m_per_s=dict.fromkeys(VALENCE, 0.0),
                    law="cells.route.constant_field@1",
                    pump=None,
                    calcium_pump=None,
                )
            ],
            junctions=[],
            faces=[],
            closure=dict(
                law="cells.field_closure.resolved_capacitor_components_current_continuity@1", gauge_reference=None
            ),
            channels=channels,
        ),
        experiment=dict(
            end_time=1e-4,
            observation_times=[0.0, 1e-4],
            membrane_controls=[dict(membrane_id="patch", schedule=always)],
            junction_controls=[],
            pump_controls=[],
            calcium_pump_controls=[],
            channel_controls=[dict(channel_id=c["id"], schedule=always) for c in channels],
        ),
        execution=dict(
            dt=1e-5,
            capacity=1,
            extracellular_capacity=1,
            membrane_capacity=1,
            edge_capacity=0,
            face_capacity=0,
            channel_capacity=len(channels),
            backend="cpu",
            jit=True,
            precision="float64",
            solver="rk4",
            field_solver="cells.solver.capacitive_reduction_gauged_damped_newton@2",
            max_steps=18,
            max_trace_bytes=2**31,
            material_balance_atol_fmol=dict.fromkeys(VALENCE, 1e-10),
        ),
    )


# --- The compiled clamp and its half crossing ----------------------------------------------------


class Clamp:
    """The compiled clamped programs, one per model implementation. A new Clamp traces anew, so a
    plant in the engine's code is seen."""

    def __init__(self):
        self.programs = {}

    def bind(self, raw):
        """(current(volts) -> [blocked, free] (A, outward-positive), the world's layout)."""
        spec = parse_spec(raw)
        model = get_model(spec.model)
        state, layout = model.initial_values(spec)
        control = model.Control(*(v[0] for v in control_values(spec, [0.0])))
        if id(model) not in self.programs:
            self.programs[id(model)] = jax.jit(partial(model.clamped_channel_flux, xp=jnp))
        program = self.programs[id(model)]

        def current(volts):
            value = np.asarray(program(state, control, layout, volts)[1])
            if value.dtype != np.float64 or value.shape != (2,):
                raise TypeError(f"The clamp returned {value.dtype} {value.shape}")
            return value

        return current, layout


def half_crossing(pair):
    """Where pair(volts) = (blocked current, free current) has the ratio 0.5: the crossing (mV),
    the ratio there minus 0.5, and the root-find's record."""

    def excess(volts):
        blocked, free = pair(volts)
        if not (math.isfinite(blocked) and math.isfinite(free) and free != 0.0):
            raise ArithmeticError(f"No ratio at {volts} V: blocked {blocked}, free {free}")
        return float(blocked / free) - HALF

    low, high = (excess(v) for v in BRACKET_V)
    if not low > 0.0 > high:
        raise ArithmeticError(f"The bracket holds no falling half crossing: {low}, {high}")
    root, record = brentq(
        excess, *BRACKET_V, xtol=1e-16, rtol=4 * np.finfo(float).eps, maxiter=200, full_output=True
    )
    if not record.converged:
        raise ArithmeticError("The root-find did not converge")
    return dict(
        crossing_mV=1000.0 * root,
        ratio_minus_half=excess(root),
        evaluations=record.function_calls,
        in_the_laws_window=VOLTAGE_DOMAIN_V[0] <= root <= VOLTAGE_DOMAIN_V[1],
    )


def closed_form_crossing_mV(calibration):
    """The 5.4 mM half crossing of sum_k w_k/(1 + exp(z_k (V - M_k)/(1000 R T/F))), with no engine
    and no K(0)."""
    thermal = thermal_mV(calibration["temperature_K"])

    def excess(v):
        free = (
            m["weight"] / (1.0 + math.exp(m["valence"] * (v - m["midpoint_mV"]) / thermal))
            for m in calibration["modes"]
        )
        return math.fsum(free) - HALF

    return brentq(excess, -300.0, 300.0, xtol=1e-13, rtol=4 * np.finfo(float).eps)


def run_check(worlds, *, twin=False):
    """{arm: {level: half_crossing's record}} of the six worlds worlds(arm, level). With twin, the
    free current is the unblocked twin world's own population's."""
    clamp, out = Clamp(), {}
    for arm in REFERENCE:
        out[arm] = {}
        for level in LEVELS_mM:
            world = worlds(arm, level)
            current, _ = clamp.bind(definition(world))
            pair = current
            if twin:
                free, _ = clamp.bind(definition(world, blocked=False))

                def pair(volts, blocked=current, free=free):
                    return blocked(volts)[0], free(volts)[0]

            out[arm][level] = half_crossing(pair)
    return out


# --- Section 2's criteria ------------------------------------------------------------------------


def crossing_values(run):
    return {a: {k: r["crossing_mV"] for k, r in rows.items()} for a, rows in run.items()}


def shifts(crossing):
    """{arm: {level: its crossing minus the arm's 5.4 mM crossing}} at 10 and 20 mM."""
    return {a: {k: x[k] - x[BASE_mM] for k in SHIFTED_mM} for a, x in crossing.items()}


def close(value, expected):
    return abs(value - expected) <= TOLERANCE_mV


def criteria(crossing, predicted):
    """Section 2's pass criteria on {arm: {level: crossing (mV)}}."""
    rows = {
        "the arms' 5.4 mM crossings coincide": (
            crossing["reversal"][BASE_mM] - crossing["absolute"][BASE_mM],
            0.0,
        )
    }
    for arm, moved in shifts(crossing).items():
        for level, value in moved.items():
            expected = predicted[level] if arm == "reversal" else 0.0
            rows[f"{arm} arm: the {level:g} mM shift"] = (value, expected)
    return {
        name: dict(
            value_mV=value,
            expected_mV=expected,
            deviation_mV=value - expected,
            passed=close(value, expected),
        )
        for name, (value, expected) in rows.items()
    }


# --- Section 2's plants --------------------------------------------------------------------------


@contextlib.contextmanager
def reversal_sign_flipped():
    """The engine with the block's reversal E read as -E, in this process only."""
    original = block_law.reversal_potential
    block_law.reversal_potential = lambda *args, **kwargs: -original(*args, **kwargs)
    try:
        yield
    finally:
        block_law.reversal_potential = original


def plants(calibration, honest_worlds, predicted, honest):
    """Section 2's plants: each has its text, the reading it runs, its worlds, its patch, and a
    signature(crossing, shift) -> {claim: holds} for its parenthesis. A plant's judged reading
    decides; a second reading is recorded only."""
    thermal = thermal_mV(calibration["temperature_K"])
    honest_shift = shifts(honest)

    def changed(applies, **change):
        def worlds(arm, level):
            world = honest_worlds(arm, level)
            return world | change if applies(arm, level) else world

        return worlds

    def in_reversal_arm(arm, level):
        return arm == "reversal"

    def shifts_are(scale, claim):
        return lambda crossing, shift: {
            f"{claim} at {k:g} mM": close(shift["reversal"][k], scale * predicted[k])
            for k in SHIFTED_mM
        }

    def external_moved(crossing, shift):
        moved = shift["reversal"][10.0] - honest_shift["reversal"][10.0]
        return {
            "that shift moves by 2.46 mV": f"{moved:.2f}" == "2.46",
            "by exactly (R T/F) ln(11/10)": close(
                moved, thermal * math.log(PLANTED_EXTERNAL_mM / 10.0)
            ),
        }

    def internal_moved(crossing, shift):
        moved = crossing["reversal"][BASE_mM] - honest["reversal"][BASE_mM]
        apart = crossing["reversal"][BASE_mM] - crossing["absolute"][BASE_mM]
        return {
            "its 5.4 mM crossing moves by 0.88 mV": f"{abs(moved):.2f}" == "0.88",
            "by exactly (R T/F) ln(145/150)": close(
                moved, thermal * math.log(calibration["internal_K_mM"] / PLANTED_INTERNAL_mM)
            ),
            "the arms no longer coincide": not close(apart, 0.0),
            "the shifts do not move": all(
                close(shift["reversal"][k], honest_shift["reversal"][k]) for k in SHIFTED_mM
            ),
        }

    held, rebuilt = "K(0) held at the calibration's", "K(0) rebuilt with E_0 = 0"
    unpatched, unchanged = contextlib.nullcontext, changed(lambda arm, level: False)
    voltage = dict(reference=REFERENCE["absolute"])
    still = shifts_are(0, "its shift is 0")
    other_way = shifts_are(-1, "the crossing moves the other way, by the predicted shift,")
    text = (
        "the membrane-voltage reference in the reversal arm (its shifts are 0)",
        "the reversal's sign flipped (the crossings move the other way)",
        "external K of 11 mM for 10 (that shift moves by 2.46 mV)",
        "internal K of 150 mM for 145 in the reversal arm (its 5.4 mM crossing moves by 0.88 mV, "
        "so the arms no longer coincide; the shifts do not move)",
    )
    return [
        dict(plant=1, text=text[0], reading=held, judged=True, patch=unpatched,
             worlds=changed(in_reversal_arm, **voltage), signature=still),
        dict(plant=1, text=text[0], reading=rebuilt, judged=False, patch=unpatched,
             worlds=changed(in_reversal_arm, **voltage, k0_mM=k0_mM(calibration, 0.0)),
             signature=still),
        dict(plant=2, text=text[1], reading=held, judged=True, patch=reversal_sign_flipped,
             worlds=unchanged, signature=other_way),
        dict(plant=3, text=text[2], reading="in both arms", judged=True, patch=unpatched,
             worlds=changed(lambda arm, level: level == 10.0, external_K_mM=PLANTED_EXTERNAL_mM),
             signature=external_moved),
        dict(plant=4, text=text[3], reading=held, judged=True, patch=unpatched,
             worlds=changed(in_reversal_arm, internal_K_mM=PLANTED_INTERNAL_mM),
             signature=internal_moved),
    ]  # fmt: skip


def judge_plant(plant, predicted, honest):
    with plant["patch"]():
        run = run_check(plant["worlds"])
    crossing = crossing_values(run)
    shift, rows = shifts(crossing), criteria(crossing, predicted)
    failed = [name for name, row in rows.items() if not row["passed"]]
    claims = {k: bool(v) for k, v in plant["signature"](crossing, shift).items()}
    return dict(
        plant=plant["plant"],
        text=plant["text"],
        reading=plant["reading"],
        judged=plant["judged"],
        caught=bool(failed),
        caught_by=failed,
        as_written=all(claims.values()),
        claims=claims,
        crossings_mV=crossing,
        crossings_minus_honest_mV={
            arm: {k: x[k] - honest[arm][k] for k in LEVELS_mM} for arm, x in crossing.items()
        },
        shifts_mV=shift,
        shifts_minus_honest_mV={
            arm: {k: x[k] - shifts(honest)[arm][k] for k in SHIFTED_mM} for arm, x in shift.items()
        },
        criteria=rows,
        root_find=run,
    )


# --- Provenance ----------------------------------------------------------------------------------


def git(repository, *args):
    command = ["git", "--no-optional-locks", "-C", str(repository), *args]
    return subprocess.run(command, check=True, capture_output=True, timeout=60).stdout


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def registered_inputs(repository):
    """(the inputs' record, the engine's pinned revision, the anchor), with the registration at its
    tag, and section 9's two pinned files hashed at their revision and compared with it."""
    registration = git(repository, "cat-file", "blob", f"{TAG}:{REGISTRATION}")
    section = registration.decode().split("\n## 9. ", 1)[1]
    engine, engine_tag = re.search(
        r"^\| Engine \| ([0-9a-f]{7,40}) \(`([^`]+)`\) \|$", section, re.M
    ).groups()
    rows = re.findall(
        r"^\| ([^|]+) \| `([^`]+)`, main ([0-9a-f]{7,40}), sha256 `([0-9a-f]{64})` \|$",
        section,
        re.M,
    )
    if [r[0] for r in rows] != ["Scoring code", "Calibration"]:
        raise ValueError("Section 9 does not name its two pinned files")
    pinned, anchor = {}, None
    for what, path, revision, expected in rows:
        data = git(repository, "cat-file", "blob", f"{revision}:{path}")
        pinned[what] = dict(
            path=path,
            revision=git(repository, "rev-parse", f"{revision}^{{commit}}").decode().strip(),
            sha256=sha256(data),
            section_9_sha256=expected,
            equal=sha256(data) == expected,
        )
        if what == "Calibration":
            anchor = json.loads(data)
    if not all(row["equal"] for row in pinned.values()):
        raise ValueError(f"A pinned file differs from section 9: {pinned}")
    revision = git(repository, "rev-parse", f"{engine_tag}^{{commit}}").decode().strip()
    if not revision.startswith(engine):
        raise ValueError(f"The engine's tag {engine_tag} is not section 9's {engine}")
    record = dict(
        registration=dict(
            path=REGISTRATION,
            tag=TAG,
            commit=git(repository, "rev-parse", f"{TAG}^{{commit}}").decode().strip(),
            sha256=sha256(registration),
        ),
        pinned=pinned,
    )
    return record, revision, anchor


def loaded_engine(snapshot):
    """The loaded cells modules, refused unless every one comes from the snapshot's src."""
    source = snapshot / "src" / "cells"
    files = {
        name: Path(module.__file__).resolve()
        for name, module in sys.modules.items()
        if (name == "cells" or name.startswith("cells.")) and getattr(module, "__file__", None)
    }
    foreign = {n: str(f) for n, f in files.items() if not f.is_relative_to(source)}
    if foreign or not files:
        raise ValueError(f"cells modules from outside the snapshot: {foreign}")
    return len(files)


def frozen_engine(snapshot, revision):
    """The snapshot's record, verified with its own tool, at the pinned revision and clean."""
    tool_path = snapshot / "validation" / "source_snapshot.py"
    module_spec = importlib.util.spec_from_file_location("snapshot_tool", tool_path)
    tool = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(tool)
    value = tool.verify(snapshot)
    clean = value["patch_sha256"] == sha256(b"") and not value["selected_status_porcelain_v1_z"]
    if value["git_revision"] != revision or not clean:
        raise ValueError(f"The snapshot is not a clean one of {revision}")
    return dict(
        path=str(snapshot),
        revision=value["git_revision"],
        clean=clean,
        files=len(value["files"]),
        manifest_sha256=sha256((snapshot / "SNAPSHOT.json").read_bytes()),
        verified_with="validation/source_snapshot.py:verify, the snapshot's own",
    )


def environment():
    if not jax.config.jax_enable_x64 or jax.default_backend() != "cpu":
        raise ValueError("The check runs in float64 on the CPU")
    names = ("PYTHONPATH", "JAX_ENABLE_X64", "JAX_PLATFORMS", "JAX_ENABLE_COMPILATION_CACHE")
    return dict(
        python=platform.python_version(),
        jax=jax.__version__,
        numpy=np.__version__,
        scipy=scipy.__version__,
        cpus=sorted(os.sched_getaffinity(0)),
        variables={name: os.environ.get(name) for name in names},
        command=sys.argv,
    )


def script_record():
    path = Path(__file__).resolve()
    record = dict(path=str(path), sha256=sha256(path.read_bytes()))
    with contextlib.suppress(subprocess.CalledProcessError):  # Outside a checkout: bytes alone.
        head = git(path.parent, "rev-parse", "HEAD").decode().strip()
        status = git(path.parent, "status", "--porcelain", "--", path.name).decode()
        record |= dict(head=head, committed=not status)
    return record


def write(path, value):
    def keyed(v):  # JSON's keys are text: 5.4, 10 and 20.
        if isinstance(v, dict):
            return {f"{k:g}" if isinstance(k, float) else k: keyed(x) for k, x in v.items()}
        return [keyed(x) for x in v] if isinstance(v, list | tuple) else v

    with path.open("x") as stream:
        json.dump(keyed(value), stream, indent=1, allow_nan=False)
        stream.write("\n")


def show(name, crossing, shift):
    for arm in REFERENCE:
        at = "  ".join(f"{crossing[arm][k]:+.9f}" for k in LEVELS_mM)
        by = "  ".join(f"{shift[arm][k]:+.9f}" for k in SHIFTED_mM)
        print(f"{name:34s} {arm:9s} crossings (mV) {at}   shifts (mV) {by}", flush=True)


def layout_record(world):
    """What the engine's layout holds for the blocked population of a world."""
    _, layout = Clamp().bind(definition(world))
    ion = int(np.asarray(layout.channel_block_ion)[0])
    return dict(
        temperature_K=np.asarray(layout.temperature).item(),
        weight=np.asarray(layout.channel_block_weight)[:, 0].tolist(),
        k0_mM=np.asarray(layout.channel_block_k0_mM)[:, 0].tolist(),
        signed_steepness=np.asarray(layout.channel_block_steepness)[:, 0].tolist(),
        blocker_mM=float(np.asarray(layout.channel_block_concentration_mM)[0]),
        referenced_to_reversal_of=(
            list(VALENCE)[ion] if bool(np.asarray(layout.channel_block_reversal)[0]) else None
        ),
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--repository", required=True, type=Path, help="holds the tagged inputs")
    parser.add_argument("--snapshot", required=True, type=Path, help="the frozen engine")
    parser.add_argument("--out", required=True, type=Path, help="a new directory")
    args = parser.parse_args(argv)
    args.out.mkdir(parents=True, exist_ok=False)
    snapshot = args.snapshot.resolve()

    inputs, revision, anchor = registered_inputs(args.repository)
    result = dict(
        what="FR-51's two-potassium registration, section 2: the engine check",
        utc=datetime.now(UTC).isoformat(),
        inputs=inputs,
        snapshot=frozen_engine(snapshot, revision),
        script=script_record(),
        environment=environment(),
        engine_models=[MODEL, POPULATION, block_law.LAW_ID],
    )
    loaded_engine(snapshot)

    calibration = read_calibration(anchor)
    temperature, internal = calibration["temperature_K"], calibration["internal_K_mM"]
    thermal = thermal_mV(temperature)
    e0_mV = {"reversal": thermal * math.log(BASE_mM / internal), "absolute": 0.0}
    k0 = {arm: k0_mM(calibration, e0) for arm, e0 in e0_mV.items()}
    predicted = {level: thermal * math.log(level / BASE_mM) for level in SHIFTED_mM}

    def honest_worlds(arm, level):
        return dict(
            calibration=calibration,
            reference=REFERENCE[arm],
            k0_mM=k0[arm],
            external_K_mM=level,
            internal_K_mM=internal,
        )

    engine_e0 = 1000.0 * float(
        block_law.reversal_potential(np.float64(internal), np.float64(BASE_mM), 1.0, temperature)
    )
    result["calibration"] = calibration | dict(
        E0_mV=e0_mV,
        k0_mM=k0,
        thermal_mV=thermal,
        engine_thermal_mV=1000.0 * electrochemistry.R * temperature / electrochemistry.F,
        E0_engine_law_mV=engine_e0,
        E0_anchor_file_mV=anchor["calibration"]["fit_cells_reversal_mV"],
        blocker=BLOCKER,
        engine_layout={arm: layout_record(honest_worlds(arm, BASE_mM)) for arm in REFERENCE},
    )
    result["predicted_shifts_mV"] = predicted
    result["tolerance_mV"] = TOLERANCE_mV

    # The honest crossings, recorded before any plant runs.
    run = run_check(honest_worlds)
    honest = crossing_values(run)
    honest_rows = criteria(honest, predicted)
    result["honest"] = dict(
        passed=all(row["passed"] for row in honest_rows.values()),
        crossings_mV=honest,
        shifts_mV=shifts(honest),
        criteria=honest_rows,
        root_find=run,
    )
    show("honest", honest, shifts(honest))
    write(args.out / "honest.json", result)
    if not result["honest"]["passed"]:
        result |= dict(passed=False, plants="not run: an honest criterion failed")
        write(args.out / "result.json", result)
        print("SECTION 2 FAILS: an honest criterion failed", flush=True)
        return 1

    twin_run = crossing_values(run_check(honest_worlds, twin=True))
    closed_form = closed_form_crossing_mV(calibration)
    reading = anchor["calibration"]["fit_half_voltage_mV"]
    low, high = anchor["calibration"]["fit_half_bracket_mV"]
    result["unjudged"] = dict(
        twin_world_reading=dict(
            crossings_mV=twin_run,
            largest_difference_mV=max(
                abs(twin_run[a][k] - honest[a][k]) for a in REFERENCE for k in LEVELS_mM
            ),
            criteria_pass=all(r["passed"] for r in criteria(twin_run, predicted).values()),
        ),
        closed_form=dict(
            crossing_mV=closed_form,
            engine_minus_closed_form_mV={a: x[BASE_mM] - closed_form for a, x in honest.items()},
        ),
        anchor_reading=dict(
            half_crossing_mV=reading,
            bracket_mV=[low, high],
            composition_minus_reading_mV=honest["reversal"][BASE_mM] - reading,
            composition_inside_bracket=low <= honest["reversal"][BASE_mM] <= high,
        ),
    )

    ran = []
    for plant in plants(calibration, honest_worlds, predicted, honest):
        ran.append(judge_plant(plant, predicted, honest))
        row = ran[-1]
        label = f"plant {row['plant']}, {'judged' if row['judged'] else 'second reading'}"
        show(label, row["crossings_mV"], row["shifts_mV"])
        print(f"  caught by {row['caught_by']}; as written {row['as_written']}", flush=True)
    again = crossing_values(run_check(honest_worlds))
    judged = [row for row in ran if row["judged"]]
    result |= dict(
        plants=ran,
        every_plant_caught=all(row["caught"] for row in judged),
        every_plant_as_written=all(row["as_written"] for row in judged),
        second_reading_agrees=all(row["caught"] and row["as_written"] for row in ran),
        honest_after_the_plants=dict(crossings_mV=again, equal_bit_for_bit=again == honest),
        cells_modules_from_the_snapshot=loaded_engine(snapshot),
    )
    result["passed"] = bool(
        result["honest"]["passed"]
        and result["every_plant_caught"]
        and result["every_plant_as_written"]
    )
    write(args.out / "result.json", result)
    print("SECTION 2", "PASSES" if result["passed"] else "FAILS", flush=True)
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
