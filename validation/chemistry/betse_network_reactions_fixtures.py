"""Small explicit native networks; no production component imports."""

from copy import deepcopy

SPECIES = ("Na", "A", "B", "C", "X", "Y", "Z")
VALENCE = (1, 0, 0, 0, -1, 1, 0)
ZONES = ("cell", "cell", "mit", "mit", "env", "env", "env")


def reaction(zone="cell", **changes):
    result = {
        "name": "convert",
        "reaction zone": zone,
        "reactants": ["A"],
        "reactant multipliers": [1.0],
        "Km reactants": [0.7],
        "products": ["B"],
        "product multipliers": [1.0],
        "Km products": [1.3],
        "max rate": 0.024,
        "standard free energy": "None",
    }
    result.update(changes)
    return result


def molecule(name="C", **changes):
    gad = {
        "production rate": 0.06,
        "decay rate": 0.013,
        "decay max": 0.02,
        "scale factor": 0.4,
        "apply to": "all",
        "modulator function": "None",
    }
    gad.update(changes)
    return {"name": name, "use time dilation": True, "growth and decay": gad}


def base(name="irreversible-cell"):
    return dict(
        name=name,
        reactions=[reaction()],
        growth=[],
        species_ids=list(SPECIES),
        species_valence=list(VALENCE),
        compartment_zones=list(ZONES),
        concentration_mM=[[1.1 + 0.17 * s + 0.31 * c for c in range(7)] for s in range(7)],
        volume_m3=[1e-15, 2e-15, 0.5e-15, 1e-15, 3e-15, 4e-15, 5e-15],
        cell_to_environment={0: 5, 1: 4},
        growth_targets={},
        growth_modulation={},
        time_dilation=3.0,
        temperature_K=307.0,
        gas_constant_J_mol_K=8.314,
        dt_s=0.125,
    )


def cases():
    result = []
    for zone in ("cell", "mit", "env"):
        for energy, tag in (("None", "irreversible"), (-750.0, "reversible"), (6000.0, "reverse")):
            row = base(tag + "-" + zone)
            row["reactions"] = [reaction(zone, **{"standard free energy": energy})]
            result.append(row)
        for km in (0.02, 40.0):
            row = base("product-km-" + zone + "-" + str(km))
            row["reactions"] = [
                reaction(zone, **{"standard free energy": -750.0, "Km products": [km]})
            ]
            result.append(row)
        row = base("ordinary-independent-" + zone)
        row["reactions"] = [
            reaction(
                zone,
                **{
                    "standard free energy": -350.0,
                    "reaction activators": ["X*", "Y!*"],
                    "activator Km": [0.7, 2.1],
                    "activator n": [2.0, 0.7],
                    "activator zone": ["env", "cell"],
                    "reaction inhibitors": ["Z!*"],
                    "inhibitor Km": [0.8],
                    "inhibitor n": [1.7],
                    "inhibitor zone": ["env"],
                },
            )
        ]
        result.append(row)
        row = base("independent-only-" + zone)
        row["reactions"] = [
            reaction(
                zone,
                **{
                    "reaction activators": ["Y!"],
                    "activator Km": [1.4],
                    "activator n": [2.0],
                    "activator zone": ["env"],
                },
            )
        ]
        result.append(row)
        row = base("direct-signed-" + zone)
        row["reactions"] = [
            reaction(
                zone,
                **{
                    "reaction activators": ["Y", "Na&*"],
                    "activator Km": [1.4, 0.2],
                    "activator n": [2.0, 1.0],
                    "activator zone": ["cell", "cell"],
                    "reaction inhibitors": ["Z&"],
                    "inhibitor Km": [1.0],
                    "inhibitor n": [1.0],
                    "inhibitor zone": ["env"],
                },
            )
        ]
        result.append(row)
        row = base("direct-inhibitor-cell-tag-" + zone)
        row["reactions"] = [
            reaction(
                zone,
                **{
                    "reaction inhibitors": ["X&"],
                    "inhibitor Km": [0.01],
                    "inhibitor n": [7.0],
                    "inhibitor zone": ["cell"],
                },
            )
        ]
        result.append(row)
        row = base("multi-real-coefficients-" + zone)
        row["reactions"] = [
            reaction(
                zone,
                **{
                    "standard free energy": 200.0,
                    "reactants": ["A", "C"],
                    "reactant multipliers": [2.0, 0.5],
                    "Km reactants": [0.7, 0.9],
                    "products": ["B", "A"],
                    "product multipliers": [1.5, 0.25],
                    "Km products": [0.2, 2.0],
                },
            )
        ]
        result.append(row)
    row = base("repeated-species-and-catalyst")
    row["reactions"] = [
        reaction(
            **{
                "reactants": ["A", "A"],
                "reactant multipliers": [1.0, 0.5],
                "Km reactants": [0.7, 1.2],
                "products": ["A", "B"],
                "product multipliers": [0.5, 1.0],
                "Km products": [1.2, 0.3],
            }
        )
    ]
    result.append(row)
    row = base("growth-matrix-order")
    row["reactions"] = [
        reaction("env", name="outside"),
        reaction("mit", name="organelle"),
        reaction("cell", name="first"),
        reaction("cell", name="second", **{"standard free energy": -300.0}),
    ]
    row["growth"] = [
        {"name": "A", "growth and decay": None},
        molecule("C"),
        molecule(
            "B",
            **{
                "activators": ["Y!"],
                "Km activators": [1.2],
                "n activators": [2.0],
                "zone activators": ["env"],
                "decay inhibitors": ["X"],
                "Km decay inhibitors": [0.8],
                "n decay inhibitors": [1.0],
                "zone decay inhibitors": ["cell"],
            },
        ),
    ]
    row["growth_targets"] = {"C": [True, False], "B": [False, True]}
    row["growth_modulation"] = {"C": [0.3, 1.1], "B": [1.0, 0.5]}
    result.append(row)
    for name, changes in (
        (
            "growth-zoned-regulation",
            {
                "activators": ["X", "Y!*"],
                "Km activators": [0.8, 1.3],
                "n activators": [1.0, 2.0],
                "zone activators": ["env", "cell"],
                "decay activators": ["Na"],
                "Km decay activators": [0.7],
                "n decay activators": [1.4],
                "zone decay activators": ["env"],
            },
        ),
        (
            "growth-direct-decay",
            {"decay inhibitors": ["X&"], "Km decay inhibitors": [0.5], "n decay inhibitors": [1.0]},
        ),
        ("growth-no-decay", {"decay rate": 0.0, "decay max": 0.0}),
        ("growth-named-controls", {"apply to": ["left"], "modulator function": "sampled"}),
    ):
        row = base(name)
        row["reactions"] = []
        row["growth"] = [molecule(**changes)]
        row["growth_targets"] = {"C": [True, False]}
        row["growth_modulation"] = {"C": [0.4, 1.5]}
        result.append(row)
    row = base("modern-gas-constant-explicit")
    row["reactions"] = [reaction("mit", **{"standard free energy": 6000.0})]
    row["gas_constant_J_mol_K"] = 8.31446261815324
    result.append(row)
    row = base("empty-network")
    row["reactions"] = []
    result.append(row)
    for row in result:
        for mol in row["growth"]:
            gad = mol.get("growth and decay")
            if not isinstance(gad, dict):
                continue
            if mol["name"] in row["growth_targets"] and gad["apply to"] == "all":
                gad["apply to"] = ["targets-" + mol["name"]]
            if mol["name"] in row["growth_modulation"]:
                gad["modulator function"] = "sampled"
    return result


def limitations():
    result = []
    for name, changes in (
        ("python-none-free-energy", {"standard free energy": None}),
        ("unknown-zone", {"reaction zone": "alien"}),
        ("empty-reactants", {"reactants": [], "reactant multipliers": [], "Km reactants": []}),
        ("mismatched-reactants", {"reactants": ["A", "C"]}),
        (
            "direct-inhibitor-not-last",
            {
                "reaction inhibitors": ["X&", "Y"],
                "inhibitor Km": [1.0, 1.0],
                "inhibitor n": [1.0, 1.0],
            },
        ),
        (
            "only-direct-both-groups",
            {
                "reaction activators": ["Y&"],
                "activator Km": [1.0],
                "activator n": [1.0],
                "reaction inhibitors": ["X&"],
                "inhibitor Km": [1.0],
                "inhibitor n": [1.0],
            },
        ),
        (
            "unknown-regulator-zone",
            {
                "reaction activators": ["X"],
                "activator Km": [1.0],
                "activator n": [1.0],
                "activator zone": ["alien"],
            },
        ),
    ):
        row = base(name)
        row["reactions"] = [reaction(**changes)]
        row["expected_failure"] = True
        result.append(row)
    row = base("disabled-mito-fallback")
    row["reactions"] = [reaction("mit", **{"standard free energy": 100.0})]
    row["mit_enabled"] = False
    row["expected_failure"] = False
    result.append(row)
    row = base("duplicate-overwrite")
    row["reactions"] = [reaction(), reaction(**{"max rate": 0.9})]
    row["expected_failure"] = False
    result.append(row)
    row = base("zero-reversible-substrate")
    row["reactions"] = [reaction(**{"standard free energy": 0.0})]
    row["concentration_mM"][SPECIES.index("A")][0] = 0.0
    row["expected_failure"] = False
    result.append(row)
    row = base("negative-growth-scale")
    row["reactions"] = []
    row["growth"] = [molecule(**{"scale factor": -0.4})]
    row["expected_failure"] = False
    result.append(row)
    return deepcopy(result)
