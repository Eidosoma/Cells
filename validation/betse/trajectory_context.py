"""Preservation, input mapping and source identity for the offline trajectory panel."""

import copy
import subprocess
from datetime import UTC, datetime

import alignment as a
import cluster_alignment as cluster
import cluster_evidence as evidence
import contact as c

PROTOCOL = c.HERE / "trajectory_protocol.json"
PRESERVATION = c.ROOT / "reports/ref-003d-preservation.json"
PRIOR = c.ROOT / "reports/ref-003c-closeout.json"
PRIOR_SHA = "3878ed73e01d537cc330230c980e0be86198fd6bc55cfb4d3ab7a2200ddd99ca"
ORDINARY_NAMES = (
    "time",
    "cc_time",
    "cc_env_time",
    "vm_time",
    "I_mem_time",
    "rho_cells_time",
    "rate_NaKATP_time",
    "gjopen_time",
    "dd_time",
)
FINAL_NAMES = (
    "cc_cells",
    "cc_env",
    "cc_at_mem",
    "vm",
    "I_mem",
    "rho_cells",
    "fluxes_mem",
    "fluxes_gj",
    "Dm_cells",
    "Phi_b",
)
NEW_FILES = {
    "native_observer.py",
    "trajectory_context.py",
    "trajectory.py",
    "trajectory_check.py",
    "trajectory_protocol.json",
    "test_native_observer.py",
    "test_trajectory.py",
}


def sources():
    return {
        p.name: c.sha(p)
        for p in sorted(c.HERE.iterdir())
        if p.suffix in (".py", ".json", ".svg", ".txt") and p.is_file()
    }


def authenticate():
    c.require(c.sha(PRIOR) == PRIOR_SHA, "REF-003c closeout changed")
    closed = c.read(PRIOR)
    c.require(closed["status"] == "pass", "REF-003c not closed")
    c.require(
        evidence.audit(evidence.SESSION) == closed["independent_audit"], "Prior evidence differs"
    )
    return c.authenticate_cells()


def preserve():
    old = authenticate()
    names = (
        subprocess.check_output(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z", "--", "."],
            cwd=c.ROOT,
        )
        .decode()
        .split("\0")
    )
    owned = {"validation/betse/" + name for name in NEW_FILES}
    baseline = {name: c.sha(c.ROOT / name) for name in sorted(set(names) - owned - {""})}
    c.write(
        PRESERVATION,
        {
            "schema": "cells.betse_trajectory_preservation@1",
            "status": "pass",
            "created_utc": datetime.now(UTC).isoformat(),
            "prior_closeout_sha256": PRIOR_SHA,
            "baseline_sha256": baseline,
            "accepted_sources": old["implementation_files_sha256"],
            "runtime": old["runtime"],
        },
    )


def native_geometry():
    return c.read(evidence.SESSION / "betse.json")["geometry"]


def native_protocol(case, dt):
    """Declared YAML changes only; native full initialization owns the dynamics."""
    base = copy.deepcopy(c.read(a.PROTOCOL))
    for entry in base["yaml_overrides"]:
        path, value = entry
        if path == ["init time settings", "time step"] or path == [
            "init time settings",
            "sampling rate",
        ]:
            value = dt
        if path == ["init time settings", "total time"]:
            value = c.read(PROTOCOL)["duration_s"]
        if path[:4] == ["tissue profile definition", "tissue", "default", "diffusion constants"]:
            value *= case["availability"]
        entry[1] = value
    return base


def definition(case, dt, backend):
    protocol = c.read(PROTOCOL)
    result = cluster.definition(c.read(a.PROTOCOL), c.read(cluster.PROTOCOL), native_geometry())
    result["experiment"]["end_time"] = protocol["duration_s"]
    result["experiment"]["observation_times"] = protocol["common_times_s"]
    for control in result["experiment"]["membrane_controls"]:
        control["leak"][0]["multipliers"] = dict.fromkeys(("Na", "K", "Cl"), case["availability"])
    result["execution"] |= {
        "dt": dt,
        "jit": backend == "jax_jit",
        "max_steps": 100,
        "max_trace_bytes": 16 * 1024 * 1024,
    }
    return result


def key(case, profile, dt):
    return f"{case}/{profile}/{dt:.8f}"


if __name__ == "__main__":
    preserve()
