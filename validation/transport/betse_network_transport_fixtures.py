"""Manufactured native-generator configurations; no tissue/isoform calibration."""

from copy import deepcopy

SPECIES = ("Na", "K", "Cl", "Ca", "A", "B", "C", "Act", "Aux", "Inh")
VALENCE = (1, 1, -1, 2, 0, 0, 0, 1, -1, 0)


def configuration(names=("Na",), coefficients=(1,), *, inward=None, outward=(), standard=0.0):
    return {
        "name": "probe",
        "reaction zone": "cell",
        "reactants": list(names),
        "reactant multipliers": list(coefficients),
        "Km reactants": [20.0 + 3 * i for i in range(len(names))],
        "products": list(names),
        "product multipliers": list(coefficients),
        "Km products": [30.0 + 5 * i for i in range(len(names))],
        "transfered out of cell": list(outward),
        "transfered into cell": list(names if inward is None else inward),
        "max rate": 1e-5,
        "standard free energy": standard,
        "ignore ECM": False,
        "apply to": "all",
    }


def cases():
    base = dict(
        inside_mM=dict(
            zip(SPECIES, (12.0, 140.0, 10.0, 0.001, 2.0, 3.0, 4.0, 0.7, 0.3, 1.2), strict=True)
        ),
        outside_mM=dict(
            zip(SPECIES, (145.0, 4.0, 120.0, 2.0, 8.0, 5.0, 6.0, 10.0, 20.0, 8.0), strict=True)
        ),
        voltage_V=-0.07,
        temperature_K=298.15,
        area_m2=4e-10,
        availability=0.7,
        rho=0.8,
    )
    result = []

    def add(name, config=None, **changes):
        row = deepcopy(base)
        row.update(name=name, config=configuration() if config is None else config)
        row.update(changes)
        result.append(row)
        return row

    for label, names, coefficients in (
        ("kcc", ("K", "Cl"), (1, 1)),
        ("nkcc", ("Na", "K", "Cl"), (1, 1, 2)),
    ):
        for sign, ratio in (
            ("forward", 2.0),
            ("stall", 1.0),
            ("near-stall", 1.0000000001),
            ("reverse", 0.5),
        ):
            row = add(label + "-" + sign, configuration(names, coefficients))
            row["outside_mM"].update({s: row["inside_mM"][s] * ratio for s in names})
    for voltage in (-0.12, 0.0, 0.06):
        add("electrogenic-import-" + str(voltage), voltage_V=voltage)
    add("electrogenic-export", configuration(inward=(), outward=("Na",)))
    add("antiport-na-k", configuration(("Na", "K"), (1, 1), inward=("Na",), outward=("K",)))
    add("ncx-stoichiometry", configuration(("Na", "Ca"), (3, 1), inward=("Na",), outward=("Ca",)))
    add("neutral-import", configuration(("A",), (1,)))
    add("charged-custom-molecule", configuration(("Act",), (1,)))
    add("fractional-multipliers", configuration(("Na", "Cl"), (0.5, 0.5)))
    add("positive-standard-energy", configuration(standard=12000.0))
    add("negative-standard-energy", configuration(standard=-12000.0), temperature_K=310.0)
    for value in (-0.12, 0.06):
        add("irreversible-voltage-" + str(value), configuration(standard=None), voltage_V=value)
    add("irreversible-string-none", configuration(standard="None"))
    changed = configuration(("K", "Cl"), (1, 1))
    changed["Km products"] = [3e-6, 5e6]
    add("ignored-product-km", changed)
    dimer = configuration(("A",), (2,))
    dimer.update(products=["B"], **{"product multipliers": [1], "Km products": [7.0]})
    add("literal-q-power-conversion", dimer)
    split = configuration(("A",), (1,))
    split.update(products=["B", "C"], **{"product multipliers": [1, 1], "Km products": [3.0, 4.0]})
    add("literal-q-item-count", split)
    regulatory = (
        ("activator", ["Act"], [0.5], [2.0], [], [], []),
        ("inhibitor", [], [], [], ["Inh"], [0.8], [3.0]),
        ("independent-only", ["Act!"], [0.5], [2.0], [], [], []),
        ("regular-plus-independent", ["Act", "Aux!"], [0.5, 0.2], [2.0, 1.5], [], [], []),
        ("inhibitor-bang", [], [], [], ["Inh!"], [0.8], [3.0]),
        ("star-and-env-zone-ignored", ["Act*"], [0.5], [2.0], ["Aux*"], [0.2], [2.0]),
        ("direct-activator", ["Act&"], [0.5], [2.0], [], [], []),
        ("direct-inhibitor", [], [], [], ["Inh&"], [0.8], [3.0]),
        (
            "mixed-direct-sum",
            ["Act&", "Aux&", "A"],
            [0.5, 0.2, 1.0],
            [2.0, 1.0, 1.0],
            ["Inh&"],
            [0.8],
            [3.0],
        ),
        (
            "inhibition-with-direct-last",
            ["Act"],
            [0.5],
            [2.0],
            ["Aux", "Inh&"],
            [0.2, 0.8],
            [2.0, 3.0],
        ),
    )
    for label, a, ka, na, i, ki, ni in regulatory:
        config = configuration()
        config.update(
            {
                "transporter activators": a,
                "activator Km": ka,
                "activator n": na,
                "activator zone": ["env"] * len(a),
                "transporter inhibitors": i,
                "inhibitor Km": ki,
                "inhibitor n": ni,
                "inhibitor zone": ["env"] * len(i),
            }
        )
        add("regulation-" + label, config)
    row = add(
        "zero-activator",
        deepcopy(next(row["config"] for row in result if row["name"] == "regulation-activator")),
    )
    row["inside_mM"]["Act"] = 0.0
    add("blocked", availability=0.0)
    add("zero-rho", rho=0.0)
    config = configuration()
    config["max rate"] = 0.0
    add("zero-capacity", config)
    return result


def source_failures():
    """Native malformed-expression cases explicitly excluded by the host binder."""
    empty = configuration(inward=())
    broken = configuration()
    broken.update(
        {
            "transporter inhibitors": ["Inh&", "Aux"],
            "inhibitor Km": [0.8, 0.2],
            "inhibitor n": [3.0, 2.0],
        }
    )
    only_direct = configuration()
    only_direct.update(
        {
            "transporter activators": ["Act&"],
            "activator Km": [0.5],
            "activator n": [2.0],
            "transporter inhibitors": ["Inh&"],
            "inhibitor Km": [0.8],
            "inhibitor n": [3.0],
        }
    )
    return {
        "reversible-without-electrical-term": empty,
        "direct-inhibitor-before-regular": broken,
        "only-direct-activator-and-inhibitor": only_direct,
    }
