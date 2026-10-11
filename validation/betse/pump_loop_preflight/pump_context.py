"""A new source context; never weaken or call old current-tree acceptance guards."""

import importlib
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
c = importlib.import_module("contact")
alignment = importlib.import_module("alignment")
PROTOCOL = HERE / "protocol.json"
FAMILY = c.ROOT / "runs/spec-010-family-2026-09-16/acceptance-01"
AUDIT = c.ROOT / "runs/spec-010-family-audit-2026-09-16/audit-01"
AUDIT_SHA = "b5b8490afbcdf6c2d2f9504ce342585d378a9c1f247f3399587e325e650a92b0"
CONTACT = c.ROOT / "runs/ref-005a-pump-audit-2026-09-16/audit-01"
CONTACT_SHA = "e968f4a4cbeab64d612029bd61623ec9916d3d720f03903f169c6428dd092ffe"
GEOMETRY = c.ROOT / "runs/ref-003b1-2026-09-12/alignment-05/native_preparation.json"
GEOMETRY_FIELDS = (
    "cell_count",
    "membrane_count",
    "cell_centres_m",
    "cell_volumes_m3",
    "cell_areas_m2",
    "membrane_owners",
    "membrane_areas_m2",
)


def prerequisites():
    result = {}
    for name, directory, expected in (
        ("family", AUDIT, AUDIT_SHA),
        ("pump_source_contact", CONTACT, CONTACT_SHA),
    ):
        c.require(c.sha(directory / "completion.json") == expected, "Prior receipt changed")
        done = c.read(directory / "completion.json")
        c.require(not (directory / "failure.json").exists(), "Prior failure present")
        c.require(
            all(c.sha(directory / n) == h for n, h in done["files_sha256"].items()),
            "Prior payload changed",
        )
        result[name] = dict(path=str(directory.relative_to(c.ROOT)), completion_sha256=expected)
    c.require(
        c.sha(FAMILY / "completion.json")
        == "0901fb6ce8facddf4701bd32534d361fef60832c8dbf8427b0aaeab2aa26eb1f",
        "Reviewed family capture changed",
    )
    c.require(
        all(
            c.sha(FAMILY / n) == h
            for n, h in c.read(FAMILY / "completion.json")["files_sha256"].items()
        ),
        "Family payload changed",
    )
    captured = c.read(FAMILY / "registration.json")["sources_sha256"]
    c.require(all(c.sha(c.ROOT / n) == h for n, h in captured.items()), "Reviewed sources changed")
    expected = {n for n in captured if n.startswith("src/cells/")}
    c.require(
        expected == {str(p.relative_to(c.ROOT)) for p in (c.ROOT / "src/cells").rglob("*.py")},
        "Reviewed production inventory changed",
    )
    return result


def sources():
    names = set(c.read(FAMILY / "registration.json")["sources_sha256"])
    names |= {str(p.relative_to(c.ROOT)) for p in HERE.glob("*") if p.suffix in (".py", ".json")}
    names |= {
        "validation/betse/alignment_protocol.json",
        "validation/betse/requirements-lock.txt",
        "docs/BETSE_PUMP_LOOP_PREFLIGHT.md",
        "reports/REF005B_PUMP_PREFLIGHT_HANDOFF.md",
        str(GEOMETRY.relative_to(c.ROOT)),
    }
    return {name: c.sha(c.ROOT / name) for name in sorted(names)}


def validate_protocol(p):
    c.require(p == c.read(PROTOCOL) and p["upstream_revision"] == c.REVISION, "Protocol changed")
    c.require(p["duration_s"] == p["steps"] * p["dt_s"] and p["steps"] == 8, "Clock scope")
    c.require(p["native_runs"] == len(p["variants"]) * len(p["modes"]) == 12, "Run coverage")
    c.require(p["observed_steps"] == len(p["variants"]) * p["steps"] == 48, "Step coverage")
    c.require(len({v["id"] for v in p["variants"]}) == 6, "Duplicate variant")
    c.require(
        p["cells_trajectory_runs"] == 0
        and all(
            p[k] is False
            for k in (
                "production_changed",
                "automatic_polling",
                "automatic_retry",
                "automatic_followup",
            )
        ),
        "Scope expanded",
    )


def configuration(template, p, variant, directory):
    base = c.read(alignment.PROTOCOL)
    conf = alignment.configuration(template, base, directory)
    conf["variable settings"]["temperature"] = p["temperature_K"]
    conf["internal parameters"]["alpha_NaK"] = p["alpha_mol_per_m2_s"] if variant["pump"] else 0.0
    conf["internal parameters"]["substances affect Vmem"] = True
    conf["general network"] = dict.fromkeys(
        ("reactions", "transporters", "channels", "modulators"), None
    ) | {"implement network": False, "biomolecules": []}
    for block in ("init time settings", "sim time settings"):
        conf[block].update(
            {"time step": p["dt_s"], "total time": p["duration_s"], "sampling rate": p["dt_s"]}
        )
    d = conf["tissue profile definition"]["tissue"]["default"]["diffusion constants"]
    for name, permeability in zip(base["expected_species"], p["permeability_m_per_s"], strict=True):
        d["Dm_" + name] = permeability * base["thickness_m"] if variant["leak"] else 0.0
    return conf
