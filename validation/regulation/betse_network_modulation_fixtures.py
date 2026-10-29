"""Explicit small control networks, independent of production modules."""

from copy import deepcopy

SPECIES = ("Na", "K", "Cl", "A", "B", "Z")
VALENCE = (1.0, 1.0, -1.0, -2.0, 0.0, 0.5)
IONS = ("Na", "K", "Cl")


def modulator(target="GJ", name="control", **changes):
    row = {"name": name, "target": target, "max effect": 0.73, "target ion": None}
    row.update(changes)
    return row


def channel(name="channel", **changes):
    row = {
        "name": name,
        "channel class": "ML",
        "channel type": "Probe",
        "max Dm": 2e-18,
        "apply to": "all",
        "init active": True,
    }
    row.update(changes)
    return row


def base(name="unregulated-GJ"):
    return dict(
        name=name,
        modulators=[modulator()],
        channels=[],
        species_ids=list(SPECIES),
        species_valence=list(VALENCE),
        ion_ids=list(IONS),
        membrane_to_environment=[3, 1, 3],
        environment_count=5,
        tj_targets=[True, False, True, False, True],
        channel_targets={},
        sample_mM=[[0.2 + 0.31 * s + 0.17 * j for j in range(8)] for s in range(6)],
        voltage_V=[-0.07, 0.015, -0.02],
        faraday_C_mol=96485.0,
        gas_constant_J_mol_K=8.314,
        temperature_K=310.0,
        sim_temperature_K=299.0,
        initialization=False,
        initial_gj=[0.3, -0.2, 1.8],
        initial_nak=[-1.0, 0.8, 0.5],
        initial_tj=[[0.1 + 0.1 * i + 0.03 * j for j in range(5)] for i in range(3)],
        initial_channel_modulator=[0.41, 0.53, 0.67],
        core_P=[0.2, 0.45, 0.8],
        relative_permeability=[1.0, 0.4, 0.2],
    )


def cases():
    result = []
    for target in ("GJ", "Na/K-ATPase", "TJ"):
        for tag, fields in (
            ("unregulated", {}),
            (
                "zoned",
                {
                    "activators": ["A*", "B!"],
                    "activator Km": [0.8, 1.3],
                    "activator n": [2.0, 0.7],
                    "activator zone": ["env", "cell"],
                    "inhibitors": ["Z!*"],
                    "inhibitor Km": [0.6],
                    "inhibitor n": [1.4],
                    "inhibitor zone": ["env"],
                },
            ),
            (
                "direct-signed",
                {
                    "activators": ["B", "Na&*"],
                    "activator Km": [0.5, 1.0],
                    "activator n": [1.0, 1.0],
                    "activator zone": ["cell", "cell"],
                    "inhibitors": ["A&"],
                    "inhibitor Km": [1.0],
                    "inhibitor n": [1.0],
                    "inhibitor zone": ["env"],
                },
            ),
            (
                "direct-cell-inhibitor",
                {
                    "inhibitors": ["A&"],
                    "inhibitor Km": [0.3],
                    "inhibitor n": [3.0],
                    "inhibitor zone": ["cell"],
                },
            ),
            (
                "independent-only",
                {"activators": ["B!"], "activator Km": [0.8], "activator n": [2.0]},
            ),
        ):
            row = base(tag + "-" + target.replace("/", "-"))
            row["modulators"] = [modulator(target, **fields)]
            result.append(row)
    row = base("ordered-overwrites")
    row["modulators"] = [
        modulator("GJ", "gj-first", **{"max effect": 2.0}),
        modulator("TJ", "tj-all", **{"max effect": 0.2}),
        modulator("TJ", "tj-K", **{"target ion": "K", "max effect": -0.7}),
        modulator("Na/K-ATPase", "pump-first", **{"max effect": -0.1}),
        modulator("GJ", "gj-last", **{"max effect": -0.3}),
        modulator("Na/K-ATPase", "pump-last", **{"max effect": 1.8}),
        modulator("TJ", "tj-Na", **{"target ion": "Na", "max effect": 0.9}),
    ]
    result.append(row)
    row = base("all-ion-last-overwrite")
    row["modulators"] = [
        modulator("TJ", "single", **{"target ion": "K", "max effect": -0.7}),
        modulator("TJ", "all", **{"target ion": "None", "max effect": 1.2}),
    ]
    result.append(row)
    row = base("empty-target-set")
    row["modulators"] = [modulator("TJ")]
    row["tj_targets"] = [False] * 5
    result.append(row)
    for cls in ("Na", "K", "Cl", "Ca", "Fun", "Cat", "ML"):
        row = base("channel-dispatch-" + cls)
        row.update(modulators=[], channels=[channel(**{"channel class": cls})])
        result.append(row)
    for name, changes in (
        (
            "channel-voltage-zones",
            {
                "channel activators": ["A*", "B!*"],
                "activator Km": [0.8, 1.1],
                "activator n": [1.2, 2.0],
                "activator zone": ["env", "cell"],
                "channel inhibitors": ["Cl*"],
                "inhibitor Km": [0.7],
                "inhibitor n": [1.4],
                "inhibitor zone": ["cell"],
            },
        ),
        (
            "channel-one-floor",
            {
                "channel inhibitors": ["A"],
                "inhibitor Km": [0.8],
                "inhibitor n": [2.0],
                "inhibitor max": [0.2],
            },
        ),
        (
            "channel-two-floors",
            {
                "channel inhibitors": ["A", "Z*"],
                "inhibitor Km": [0.8, 1.2],
                "inhibitor n": [2.0, 1.0],
                "inhibitor zone": ["cell", "env"],
                "inhibitor max": [0.2, 0.3],
            },
        ),
        (
            "channel-three-floors",
            {
                "channel inhibitors": ["A", "Z", "Na"],
                "inhibitor Km": [0.8, 1.2, 0.2],
                "inhibitor n": [2.0, 1.0, 0.7],
                "inhibitor max": [0.2, 0.0, -0.4],
            },
        ),
        (
            "channel-activator-maximum-ignored",
            {
                "channel activators": ["B"],
                "activator Km": [0.7],
                "activator n": [1.0],
                "activator max": [-3.0],
            },
        ),
        (
            "channel-direct-inhibitor-last",
            {
                "channel activators": ["B", "Na&*"],
                "activator Km": [0.6, 0.2],
                "activator n": [1.0, 1.0],
                "channel inhibitors": ["Z", "A&*"],
                "inhibitor Km": [1.0, 1.0],
                "inhibitor n": [2.0, 1.0],
                "inhibitor max": [0.3, 0.9],
            },
        ),
        ("channel-named-profile", {"apply to": ["subset"]}),
        ("channel-express-maxDm-unscaled", {"apply to": "express"}),
        ("channel-conductivity-precedence", {"max conductivity": 9e-18, "max Dm": 2e-18}),
        ("channel-init-inactive", {"init active": False}),
    ):
        row = base(name)
        row.update(modulators=[], channels=[channel(**changes)])
        if name == "channel-named-profile":
            row["channel_targets"] = {"channel": [True, False, True]}
        elif name == "channel-express-maxDm-unscaled":
            row["channel_targets"] = {"channel": [True] * 3}
        elif name == "channel-init-inactive":
            row["initialization"] = True
        result.append(row)
    row = base("mixed-channels-controls")
    row["modulators"] = [modulator("GJ"), modulator("TJ", "tj", **{"target ion": "Cl"})]
    row["channels"] = [
        channel(
            "first", **{"channel activators": ["A*"], "activator Km": [0.8], "activator n": [1.0]}
        ),
        channel("second", **{"init active": False}),
    ]
    row["initialization"] = True
    result.append(row)
    row = base("zero-regulator")
    row["modulators"] = [
        modulator(**{"activators": ["B"], "activator Km": [0.7], "activator n": [2.0]})
    ]
    row["sample_mM"][SPECIES.index("B")][:3] = [0.0] * 3
    result.append(row)
    row = base("empty-network")
    row.update(modulators=[], channels=[])
    result.append(row)
    return deepcopy(result)


def limitations():
    result = []
    for target in ("gj", "Na/K-ATP", "MT", "H/K-ATPase"):
        row = base("unsupported-" + target.replace("/", "-"))
        row["modulators"] = [modulator(target)]
        result.append(row)
    for name, changes in (
        ("unknown-TJ-ion", {"target": "TJ", "target ion": "unknown"}),
        (
            "direct-inhibitor-not-last",
            {"inhibitors": ["A&", "B"], "inhibitor Km": [1.0, 1.0], "inhibitor n": [1.0, 1.0]},
        ),
        (
            "direct-both-only",
            {
                "activators": ["B&"],
                "activator Km": [1.0],
                "activator n": [1.0],
                "inhibitors": ["A&"],
                "inhibitor Km": [1.0],
                "inhibitor n": [1.0],
            },
        ),
        (
            "unknown-regulator-zone",
            {
                "activators": ["B"],
                "activator Km": [1.0],
                "activator n": [1.0],
                "activator zone": ["alien"],
            },
        ),
    ):
        row = base(name)
        row["modulators"] = [modulator(**changes)]
        result.append(row)
    row = base("duplicate-name-overwrite")
    row["modulators"] = [
        modulator(name="same"),
        modulator("Na/K-ATPase", "other"),
        modulator(name="same", **{"max effect": -0.9}),
    ]
    row["expected_failure"] = False
    result.append(row)
    row = base("TJ-uninitialized-live-array")
    row["modulators"] = [modulator("TJ")]
    row["uninitialized_TJ"] = True
    result.append(row)
    for name, changes in (
        ("unsupported-channel-class", {"channel class": "NaP"}),
        ("unknown-channel-type", {"channel type": "Missing"}),
        ("missing-sim-dyna", {"apply to": ["subset"]}),
        (
            "channel-maxima-short",
            {
                "channel inhibitors": ["A", "B"],
                "inhibitor Km": [1.0, 1.0],
                "inhibitor n": [1.0, 1.0],
                "inhibitor max": [0.2],
            },
        ),
    ):
        row = base(name)
        row.update(modulators=[], channels=[channel(**changes)])
        row["channel_targets"] = {"channel": [True, False, True]}
        if name == "missing-sim-dyna":
            row["missing_sim_dyna"] = True
        result.append(row)
    for row in result:
        row.setdefault("expected_failure", True)
    return deepcopy(result)
