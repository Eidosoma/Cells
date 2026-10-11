"""Source-bound measured geometry/chemistry mapping, with no simulator imports."""

import hashlib
import importlib
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
c = importlib.import_module("contact")
PROTOCOL = HERE / "protocol.json"
CAPTURE = c.ROOT / "runs/ref-005b-pump-loop-2026-09-16/capture-01"
AUDIT = c.ROOT / "runs/ref-005b-pump-loop-audit-2026-09-16/audit-01"
AUDIT_SHA = "ca6e0f6535531ac772ea4d55e81a251d3b25fc8e4cefc2ec7987a6a357b9065e"
CAPTURE_SHA = "25080e882abfd303b4559132dd94512defa4793305e608afd906c9aeae3359c0"
F, R = 96485.33212331001, 8.31446261815324
STATE_FIELDS = (
    "amount_increment",
    "leak_transferred",
    "pump_cycles",
    "dissipated_energy_pJ",
    "gate",
    "channel_transferred",
    "junction_gate",
    "junction_transferred",
    "junction_dissipated_energy_pJ",
    "extracellular_amount_increment",
)


def key(identifier, step):
    return identifier + "/dt_" + format(step, ".8g")


def digest(value):
    import json

    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def prior():
    c.require(
        c.sha(AUDIT / "completion.json") == AUDIT_SHA
        and c.sha(CAPTURE / "completion.json") == CAPTURE_SHA,
        "Prior identities changed",
    )
    for directory in (AUDIT, CAPTURE):
        c.require(not (directory / "failure.json").exists(), "Prior failure present")
        c.require(
            all(
                c.sha(directory / n) == h
                for n, h in c.read(directory / "completion.json")["files_sha256"].items()
            ),
            "Prior payload changed",
        )
    r = c.read(CAPTURE / "registration.json")
    c.require(
        all(c.sha(c.ROOT / n) == h for n, h in r["sources_sha256"].items()),
        "Preserved sources changed",
    )
    modules = {n for n in r["sources_sha256"] if n.startswith("src/cells/")}
    c.require(
        len(modules) == 55
        and modules == {str(p.relative_to(c.ROOT)) for p in (c.ROOT / "src/cells").rglob("*.py")},
        "Production inventory changed",
    )
    return dict(audit_completion_sha256=AUDIT_SHA, capture_completion_sha256=CAPTURE_SHA)


def sources():
    names = set(c.read(CAPTURE / "registration.json")["sources_sha256"])
    names |= set(c.read(AUDIT / "registration.json")["source_sha256"])
    names |= {str(p.relative_to(c.ROOT)) for p in HERE.glob("*") if p.suffix in (".py", ".json")}
    names |= {
        "docs/BETSE_MATCHED_PUMP_PILOT.md",
        "reports/REF005B_PUMP_LOOP_CLOSEOUT.md",
        "reports/REF005C_MATCHED_PUMP_HANDOFF.md",
    }
    return {name: c.sha(c.ROOT / name) for name in sorted(names)}


def native_rows():
    return c.read(CAPTURE / "betse.json")["rows"]


def uniform(values):
    c.require(
        values and all(math.isfinite(v) and v == values[0] for v in values),
        "Cannot aggregate nonuniform native values",
    )
    return values[0]


def owners(values, g):
    c.require(len(values) == g["membrane_count"], "Face axis mismatch")
    return [
        uniform([v for v, o in zip(values, g["membrane_owners"], strict=True) if o == i])
        for i in range(g["cell_count"])
    ]


def case_for(row, variant, *, physical=None, end=0.001):
    g = row["geometry"]
    p = row["trace"]["initial"]["physical"] if physical is None else physical
    n = g["cell_count"]
    c.require(
        n == 7 and g["membrane_count"] == 30 and row["settings"]["constants"] == dict(F=F, R=R),
        "Mapping scope",
    )
    for s in range(6):
        c.require(
            owners(p["at_membrane_mM"][s], g) == p["inside_mM"][s],
            "Not a whole-cell uniform membrane",
        )
    vi = [v / 1e-15 for v in g["cell_volumes_m3"]]
    vo = g["effective_bath_volume_m3"] / 1e-15
    co = [uniform(v) for v in p["outside_mM"]]
    area = g["cell_areas_m2"]
    fractions = [
        1.0
        if variant["cluster_open"]
        else math.fsum(
            a
            for j, (a, o) in enumerate(
                zip(g["membrane_areas_m2"], g["membrane_owners"], strict=True)
            )
            if o == i and j not in g["boundary_faces"]
        )
        / area[i]
        for i in range(n)
    ]
    c.require(all(0 <= v <= 1 for v in fractions), "Active membrane area fraction")
    params = row["settings"]["pump_parameters"]
    permeabilities = [owners(v, g) for v in row["metadata"]["ordinary_diffusivity_m2_per_s"][:3]]
    return dict(
        id=variant["id"],
        species=["Na", "K", "Cl"],
        valence=[1, 1, -1],
        pump_stoichiometry=[-3, 2, 0],
        sodium_index=0,
        potassium_index=1,
        temperature_K=row["settings"]["temperature_K"],
        volume_pL=vi,
        outside_volume_pL=vo,
        initial_inside_mM=[[p["inside_mM"][s][i] for s in range(3)] for i in range(n)],
        initial_outside_mM=co[:3],
        initial_voltage_V=owners(p["voltage_V"], g),
        fixed_inside_charge_fmol=[
            math.fsum(
                [
                    2 * p["inside_mM"][3][i] * vi[i],
                    -p["inside_mM"][4][i] * vi[i],
                    -p["inside_mM"][5][i] * vi[i],
                ]
            )
            for i in range(n)
        ],
        fixed_outside_charge_fmol=math.fsum([2 * co[3] * vo, -co[4] * vo, -co[5] * vo]),
        area_m2=area,
        specific_capacitance_F_m2=[g["specific_capacitance_F_per_m2"]] * n,
        active_area_fraction=fractions,
        permeability_m_s=[
            [permeabilities[s][i] / row["settings"]["thickness_m"] * fractions[i] for s in range(3)]
            for i in range(n)
        ],
        alpha_mol_m2_s=[
            row["settings"]["alpha_NaK"] * variant["rho_pump"] * fraction for fraction in fractions
        ],
        atp_mM=[params["cATP"]] * n,
        adp_mM=[params["cADP"]] * n,
        pi_mM=[params["cPi"]] * n,
        km_na_mM=[params["KmNK_Na"]] * n,
        km_k_mM=[params["KmNK_K"]] * n,
        km_atp_mM=[params["KmNK_ATP"]] * n,
        delta_g0_J_mol=[params["deltaGATP"]] * n,
        end_time_s=end,
        controls=[dict(time_s=0.0, pump=1.0, leak=1.0)],
    )


def cases():
    rows = native_rows()
    variants = c.read(CAPTURE / "registration.json")["protocol"]["variants"]
    return {v["id"]: case_for(rows[v["id"] + "/observed"], v) for v in variants}


def definition(case, dt, *, jit=True, times=None):
    p = c.read(PROTOCOL)
    ids = case["species"]

    def mapped(values):
        return dict(zip(ids, values, strict=True))

    entries = []
    for i, volume in enumerate(case["volume_pL"]):
        pump = dict(
            id=f"pump_{i}",
            law="nak_atp_mass_action_positive@1",
            roles=dict(sodium="Na", potassium="K"),
            stoichiometry={"Na": -3, "K": 2},
            capacity_fmol_per_s=case["area_m2"][i] * case["alpha_mol_m2_s"][i] * 1e15,
            **{k: case[k][i] for k in ("km_na_mM", "km_k_mM", "km_atp_mM")},
            metabolism=dict(
                kind="maintained_chemical_reservoirs@1",
                **{k: case[k][i] for k in ("atp_mM", "adp_mM", "pi_mM")},
                delta_g0_J_per_mol=case["delta_g0_J_mol"][i],
            ),
        )
        entries.append(
            dict(
                cell=dict(
                    id=f"cell_{i}",
                    volume_pL=volume,
                    initial_amount_fmol=mapped([x * volume for x in case["initial_inside_mM"][i]]),
                    initial_voltage_V=case["initial_voltage_V"][i],
                    fixed_charge_equivalent_fmol=case["fixed_inside_charge_fmol"][i],
                ),
                membrane=dict(
                    id=f"membrane_{i}",
                    inside=f"cell_{i}",
                    outside="outside",
                    area_m2=case["area_m2"][i],
                    specific_capacitance_F_per_m2=case["specific_capacitance_F_m2"][i],
                    passive=dict(
                        law="constant_field@1",
                        permeability_m_per_s=mapped(case["permeability_m_s"][i]),
                    ),
                    pump=pump,
                ),
                channel=None,
            )
        )
    return dict(
        schema_version=1,
        model=dict(
            id="finite_extracellular@2",
            species=[
                dict(id=name, valence=z) for name, z in zip(ids, case["valence"], strict=True)
            ],
            temperature_K=case["temperature_K"],
            extracellular=dict(
                id="outside",
                volume_pL=case["outside_volume_pL"],
                initial_amount_fmol=mapped(
                    [x * case["outside_volume_pL"] for x in case["initial_outside_mM"]]
                ),
                fixed_charge_equivalent_fmol=case["fixed_outside_charge_fmol"],
            ),
            cells=entries,
            junctions=[],
        ),
        experiment=dict(
            end_time=case["end_time_s"],
            observation_times=p["common_times_s"] if times is None else times,
            membrane_controls=[
                dict(
                    membrane_id=f"membrane_{i}",
                    leak=[dict(time=0.0, multipliers=dict.fromkeys(ids, 1.0))],
                    pump=[dict(time=0.0, multiplier=1.0)],
                )
                for i in range(len(entries))
            ],
            channel_controls=[],
            junction_controls=[],
        ),
        execution=dict(
            dt=dt,
            jit=jit,
            capacity=8,
            membrane_capacity=9,
            channel_capacity=2,
            edge_capacity=2,
            extracellular_capacity=2,
            backend="cpu",
            precision="float64",
            solver="rk4",
            max_steps=p["resources"]["max_cells_steps"],
            max_trace_bytes=p["resources"]["max_cells_trace_bytes"],
            material_balance_atol_fmol=dict.fromkeys(ids, p["accounting"]["cells_material_fmol"]),
        ),
    )


def runtime():
    from importlib import metadata

    return dict(
        python=sys.version,
        packages={
            n: metadata.version(n)
            for n in ("numpy", "jax", "jaxlib", "scipy", "ml_dtypes", "opt_einsum")
        },
    )
