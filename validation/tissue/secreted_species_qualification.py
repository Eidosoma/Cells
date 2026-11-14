"""D150 version 1's numerical qualification: the held sphere against its closed forms.

docs/SECRETED_SPECIES_TRANSPORT_DESIGN.md §6, §7 and §12, the lead's rulings; the protocol is
validation/tissue/secreted_species_protocol.json, drafted by validation/tissue/
secreted_species_protocol.py from this driver's development runs.

**The world** (validation/tissue/secreted_species_radial). A sphere of radius R = 10 um is held at
c0 = 1e-3 mM by a bath; the medium has D = 4e-10 m^2/s and first-order clearance k = 1/s (lambda =
20 um) by scheduled_species_turnover@1 at every shell; shells of width dr run out to R + 6 lambda =
130 um, where an outer bath holds the trace 1e-15 mM. Every face carries the exact spherical-shell
conductance between the points it joins. The ions are quiescent (the species-only world).

**The start** is resolved (the lead's ruling 5): the steady state plus two positive sine modes of
v = r u, v(r, 0) = v_ss + a_1 sin(pi s / L) + a_2 sin(2 pi s / L) with a_1 = 0.5 R c0 and
a_2 = 0.2 R c0 (s = r - R, L = 120 um). It meets both boundary conditions, so the source holds c0 at
t = 0 too, and the closed form is a finite sum (validation/tissue/secreted_species_closed_forms).
Each shell starts at the start's exact shell average.

**References** (independent NumPy): the exact solution of each arm's own declared finite-volume
system (the matrix exponential, secreted_species_radial.solution) and the continuum closed forms
(shell averages, M, the baths' supplies and the clearance).

**Arms** (ARMS): IMEX ARS(2,2,2) at dr 5, 2.5 and 1.25 um and dt 1, 0.5 and 0.25 ms; RK4 at dr 2.5
um, dt 0.1 and 0.05 ms; and the negative control, the probes' planar faces at dr 2.5 um, 1 ms. Each
arm runs through the runner with every host check, so its energy, material and domain checks pass on
every accepted row or the run is refused.

Usage (PYTHONPATH at the source tree under test):
  python -m validation.tissue.secreted_species_qualification develop OUT [ARM ...]
  python -m validation.tissue.secreted_species_qualification analyse OUT
  python -m validation.tissue.secreted_species_qualification judge OUT   (after registration only)
  python -m validation.tissue.secreted_species_qualification judge-q5 OUT   (after registration)
  python -m validation.tissue.secreted_species_qualification combine OUT Q1_Q2_Q3_OUT Q5_OUT

The three judged entries (secreted_species_protocol.judge, judge_q5 and combine) each refuse an
unregistered protocol, a source other than a clean execution snapshot and an existing OUT before
anything runs; combine writes the one qualification verdict from the other two.
"""

import json
import math
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

from validation.tissue import secreted_species_closed_forms as cf
from validation.tissue import secreted_species_fixtures as fx
from validation.tissue import secreted_species_radial as radial

ROOT = Path(__file__).resolve().parents[2]
R, D, K, C0, TRACE = 10e-6, 4e-10, 1.0, 1e-3, 1e-15
OUTER = R + 6 * math.sqrt(D / K)  # 130 um.
MODES = ((1, 0.5 * R * C0), (2, 0.2 * R * C0))
RECORDS = (0.25, 0.5, 1.0, 2.0, 4.0)
RK4_RECORDS = (0.25, 0.5)
COARSE = radial.Geometry(R, 5e-6, 24)  # The coarse shells every grid aggregates onto.
EPS = float(np.finfo(float).eps)
FLOOR_K = 64  # A floor of 64 eps x the quantity's scale, as S5's.
# name: (shell width m, dt s, solver, faces, end s)
ARMS = {
    "dr5_dt0.5": (5e-6, 5e-4, fx.IMEX, "exact", 4.0),
    "dr2.5_dt1": (2.5e-6, 1e-3, fx.IMEX, "exact", 4.0),
    "dr2.5_dt0.5": (2.5e-6, 5e-4, fx.IMEX, "exact", 4.0),
    "dr2.5_dt0.25": (2.5e-6, 2.5e-4, fx.IMEX, "exact", 4.0),
    "dr1.25_dt0.5": (1.25e-6, 5e-4, fx.IMEX, "exact", 4.0),
    "rk4_dr2.5_dt0.1": (2.5e-6, 1e-4, "rk4", "exact", 0.5),
    "rk4_dr2.5_dt0.05": (2.5e-6, 5e-5, "rk4", "exact", 0.5),
    "planar_dr2.5_dt1": (2.5e-6, 1e-3, fx.IMEX, "planar", 4.0),
}
JUDGED = ("dr2.5_dt1", "rk4_dr2.5_dt0.1")  # The judged configuration's two arms.


def problem():
    return cf.HeldSphere(R, OUTER, D, K, C0, TRACE, MODES)


def geometry(width):
    return radial.Geometry(R, width, int(round((OUTER - R) / width)))


def records(name):
    return RK4_RECORDS if ARMS[name][2] == "rk4" else RECORDS


def arm_world(name, *, end=None, times=None):
    """The arm's world. end and times (the records after t = 0) override the arm's own, for the
    step-map guard's shortened arms; omitted, the arm's world is unchanged."""
    width, dt, solver, faces, arm_end = ARMS[name]
    g = geometry(width)
    return radial.world(
        g,
        diffusivity=D,
        clearance=K,
        c0_mM=C0,
        trace_mM=TRACE,
        profile_mM=problem().shell_averages(g.edges, 0.0),
        dt=dt,
        end=arm_end if end is None else end,
        solver=solver,
        observation_times=[0.0, *(records(name) if times is None else times)],
        faces=faces,
    )


def source_identity():
    """The run's source: the execution snapshot's manifest, or the checkout's Git state."""
    manifest = ROOT / "SNAPSHOT.json"
    if manifest.exists():
        snapshot = json.loads(manifest.read_text())
        return dict(
            kind="snapshot",
            git_revision=snapshot.get("git_revision"),
            patch_sha256=snapshot.get("patch_sha256"),
            status=snapshot.get("status"),
        )
    try:
        head = subprocess.run(
            ["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True
        ).stdout.strip()
        dirty = subprocess.run(
            ["git", "-C", str(ROOT), "status", "--porcelain"], capture_output=True, text=True
        ).stdout.strip()
    except OSError:
        head, dirty = None, None
    return dict(kind="checkout", git_revision=head, dirty=bool(dirty))


def run_arm(name, *, end=None, times=None):
    """One arm through the runner (every host check): its records as a JSON-ready dict (end and
    times as in arm_world)."""
    import jax

    jax.config.update("jax_enable_x64", True)
    from cells.core.runner import run
    from cells.core.specs import parse_spec

    spec = parse_spec(arm_world(name, end=end, times=times))
    started = time.perf_counter()
    result = run(spec)
    seconds = time.perf_counter() - started
    s = list(spec.model.species_ids).index(fx.SPECIES)
    ids = [o.id for o in spec.model.extracellular]
    width = ARMS[name][0]
    cols = [ids.index(f"shell_{i}") for i in range(geometry(width).shells)]
    obs = result.observations
    supplied = np.asarray(obs.reservoir_supplied)[:, s]
    return dict(
        arm=name,
        width_m=width,
        dt_s=ARMS[name][1],
        solver=ARMS[name][2],
        faces=ARMS[name][3],
        times_s=np.asarray(obs.times).tolist(),
        shell_amounts_fmol=np.asarray(obs.extracellular_amount)[:, s][:, cols].tolist(),
        source_supplied_fmol=supplied[:, ids.index("source")].tolist(),
        outer_supplied_fmol=supplied[:, ids.index("outer")].tolist(),
        cleared_fmol=np.asarray(obs.turnover_outside_cleared_fmol)[:, s][:, cols]
        .sum(axis=1)
        .tolist(),
        diagnostics={k: float(v) for k, v in result.diagnostics.items()},
        seconds=seconds,
        max_dt_K_ii=radial.max_dt_k(geometry(width), diffusivity=D, clearance=K, dt=ARMS[name][1]),
    )


def develop(out, names=()):
    """Run the development arms (all, or the named ones), each saved as OUT/ARM.json."""
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "source.json").write_text(json.dumps(source_identity(), indent=1) + "\n")
    for name in names or ARMS:
        if name not in ARMS:
            raise SystemExit(f"Unknown arm {name!r} (one of {sorted(ARMS)})")
        path = out / f"{name}.json"
        if path.exists():
            print(name, "exists; kept", flush=True)
            continue
        try:
            record = run_arm(name)
        except Exception as error:  # A refused arm is a finding: record it and go on.
            record = dict(arm=name, refused=f"{type(error).__name__}: {error}")
        path.write_text(json.dumps(record, indent=1) + "\n")
        print(name, record.get("seconds", record.get("refused")), flush=True)


if __name__ == "__main__":
    action, target, *rest = sys.argv[1:]
    if action == "develop":
        develop(target, rest)
    elif action == "analyse":
        from validation.tissue.secreted_species_analysis import analyse

        analyse(target)
    elif action == "judge":
        from validation.tissue.secreted_species_protocol import judge

        judge(target)
    elif action == "judge-q5":
        from validation.tissue.secreted_species_protocol import judge_q5

        judge_q5(target)
    elif action == "combine":
        from validation.tissue.secreted_species_protocol import combine

        if len(rest) != 2:
            raise SystemExit("Usage: combine OUT Q1_Q2_Q3_OUT Q5_OUT")
        combine(target, *rest)
    else:
        raise SystemExit(
            f"Unknown action {action!r} (develop, analyse, judge, judge-q5 or combine)"
        )
