"""D103 saved-data checker: explicit source-order zero-flux bath remixing.

Versioned from frozen D102 release_check.py. Unchanged input, gate, flux,
conservation and observer checks remain; no captured values are normalized.
"""

import hashlib
import importlib
import math
import struct

import release_context as ctx
import release_input as inputs
import review_math as remix

ind = importlib.import_module("loop_independent")
c, io = ctx.c, ctx.io


class Ledger(io.Ledger):
    def __init__(self, absolute):
        super().__init__(absolute, relative=absolute["relative"])
        self.identities = set()
        self.remix_records = []
        self.original_guard_rejections = []

    def compare(self, name, actual, expected, unit):
        if not isinstance(expected, list):
            c.require(name not in self.identities, "Duplicate numerical identity")
            self.identities.add(name)
        super().compare(name, actual, expected, unit)

    def add(self, name, actual, expected, unit):
        self.compare(name, actual, expected, unit)


def flat(value):
    if isinstance(value, list):
        for v in value:
            yield from flat(v)
    else:
        yield ind.finite(value)


def zero(value):
    c.require(all(v == 0 for v in flat(value)), "Nonzero blocked/inactive value")


def inventory_link(guard, snapshot):
    c.require(guard["excluded_input"] == "channel/maxDm", "Wrong numeric inventory exclusion")
    numeric = guard["numeric"]
    names = {
        "sim/" + attr: snapshot["physical"][name] for name, attr in inputs.old.PHYSICAL.items()
    }
    names |= {
        "gates/" + name: snapshot["channel"][field]
        for name, field in (
            ("m", "m"),
            ("h", "h"),
            ("P", "P"),
            ("DChan", "DChan_m2_per_s"),
            ("chan_flux", "density_mol_per_m2_s"),
        )
    }
    c.require("channel/maxDm" not in numeric, "Input was not excluded from non-mutation guard")
    for name, value in names.items():
        if value is None:
            continue
        row = numeric[name]
        shape, level = [], value
        while isinstance(level, list):
            shape.append(len(level))
            level = level[0] if level else 0.0
        raw = b"".join(struct.pack("<d", x) for x in ind.scalars(value, shape))
        c.require(
            row
            == {
                "kind": "array",
                "dtype": "<f8",
                "shape": shape,
                "bytes_sha256": hashlib.sha256(raw).hexdigest(),
            },
            "Declared native state/numeric inventory mismatch: " + name,
        )
    c.require(any(n.startswith("geometry/") for n in numeric), "Missing geometry guard")
    return len(names)


def step_metrics(prefix, row, geometry, physics, dt, maximum, weights, mode, ledger):
    g, before = geometry, row["before"]
    m = g["membrane_count"]
    constants, thickness = physics["constants"], physics["thickness_m"]
    c.require(
        row["calls"]
        == {
            "clear": 1,
            "channel": 1,
            "empty_network": 1,
            "ordinary": 1,
            "voltage": 1,
            "full_simulator_loop": 0,
        },
        "Wrong single-update scope",
    )
    cleared = row["after_clear"]
    c.require(
        cleared["physical"] == before["physical"] and cleared["channel"] == before["channel"],
        "Clear changed physical/gate state",
    )
    zero(cleared["network_current"])
    post = row["after_channel"]["channel"]
    gate_target = [
        ind.gate_values(v, [before["channel"]["m"][i], before["channel"]["h"][i]], dt)
        for i, v in enumerate(before["physical"]["voltage_V"])
    ]
    for j, name in enumerate(("m", "h")):
        ledger.add(prefix + "/gate/" + name, post[name], [g[j] for g in gate_target], "gate")
    c.require(
        post["m"] != before["channel"]["m"] or post["h"] != before["channel"]["h"],
        "Unavailable channel gates were frozen",
    )
    opened = [a * b for a, b in zip(post["m"], post["h"], strict=True)]
    ledger.add(prefix + "/open", post["P"], opened, "gate")
    diffusion = [q * maximum for q in opened]
    ledger.add(prefix + "/diffusion", post["DChan_m2_per_s"], diffusion, "diffusivity_m2_per_s")
    predicted = [
        float(
            ind.inward_density(
                before["physical"]["voltage_V"][i],
                before["physical"]["inside_mM"][1][owner],
                ind.uniform(before["physical"]["outside_mM"][1]),
                diffusion[i] / thickness,
                constants,
                physics["temperature_K"],
            )
        )
        for i, owner in enumerate(g["membrane_owners"])
    ]
    density = post["density_mol_per_m2_s"]
    ledger.add(prefix + "/density", density, predicted, "density_mol_per_m2_s")
    current = [-constants["F"] * value for value in density]
    flow = [v * 1e15 for v in ind.integrate_faces(density, g)]
    volumes = [v / 1e-15 for v in g["cell_volumes_m3"]]
    outside_volume = g["effective_bath_volume_m3"] / 1e-15
    ledger.add(
        prefix + "/network_current",
        row["after_channel"]["network_current"],
        current,
        "current_density_A_per_m2",
    )
    c.require(
        row["after_channel"]["physical"]["extra_current_density_A_per_m2"]
        == before["physical"]["extra_current_density_A_per_m2"],
        "Current exported before empty network boundary",
    )
    for stage in (
        "before",
        "after_clear",
        "after_channel",
        "after_network",
        "after_ordinary",
        "after_voltage",
    ):
        s = row[stage]
        ind.stage_metrics(ledger, prefix + "/" + stage, s, before["physical"], g)
        transferred = stage not in ("before", "after_clear")
        for species in range(6):
            increment = dt if transferred and species == 1 else 0.0
            ledger.add(
                f"{prefix}/{stage}/inside_expected/{species}",
                s["physical"]["inside_mM"][species],
                [
                    v + increment * q / volume
                    for v, q, volume in zip(
                        before["physical"]["inside_mM"][species], flow, volumes, strict=True
                    )
                ],
                "concentration_mM",
            )
            ledger.add(
                f"{prefix}/{stage}/outside_expected/{species}",
                s["physical"]["outside_mM"][species],
                [
                    ind.uniform(before["physical"]["outside_mM"][species])
                    - increment * math.fsum(flow) / outside_volume
                ]
                * m,
                "concentration_mM",
            )
        if stage in ("after_network", "after_ordinary", "after_voltage"):
            ledger.add(
                prefix + "/" + stage + "/export",
                s["physical"]["extra_current_density_A_per_m2"],
                current,
                "current_density_A_per_m2",
            )
        if stage in ("before", "after_voltage"):
            ind.direct_charge(s["physical"], g, constants)
    remix.check_zero_flux_boundaries(prefix, row, g, maximum, ledger)
    final = row["after_voltage"]["physical"]
    ledger.add(prefix + "/Jmem", final["Jmem_A_per_m2"], current, "current_density_A_per_m2")
    average = [
        q / a for q, a in zip(ind.integrate_faces(current, g), g["cell_areas_m2"], strict=True)
    ]
    smoothed = [
        w * q + wo * average[owner]
        for w, wo, q, owner in zip(*weights, current, g["membrane_owners"], strict=True)
    ]
    ledger.add(prefix + "/Jn", final["Jn_A_per_m2"], smoothed, "current_density_A_per_m2")
    ledger.add(
        prefix + "/I_mem",
        final["I_mem_A"],
        [-q * a for q, a in zip(smoothed, g["membrane_areas_m2"], strict=True)],
        "current_A",
    )
    ledger.add(
        prefix + "/voltage_increment",
        [
            a - b
            for a, b in zip(
                ind.owner_values(final["voltage_V"], g),
                ind.owner_values(before["physical"]["voltage_V"], g),
                strict=True,
            )
        ],
        [
            q * dt * constants["F"] * 1e-15 / (a * g["specific_capacitance_F_per_m2"])
            for q, a in zip(flow, g["cell_areas_m2"], strict=True)
        ],
        "voltage_V",
    )
    if maximum == 0:
        zero(density)
        zero(current)
        for field in ("inside_mM", "at_membrane_mM", "voltage_V"):
            c.require(
                final[field] == before["physical"][field],
                "Blocked physical inventory/voltage changed",
            )
    if mode == "observed":
        watch = row["observer"]
        c.require(
            watch["events"] == ["before_gate", "after_gate", "before_transfer", "after_transfer"]
            and watch["hook_restored"] is True,
            "Native gate/transfer observation incomplete",
        )
        snapshots = watch["snapshots"]
        c.require(
            set(snapshots) == {"before_gate", "after_gate", "before_transfer"},
            "Observer fields differ",
        )
        # The native network materializes its unit modulation expression before
        # entering the gate, and electroflux nudges live vm before update_Co.
        # Check these precise source-defined changes instead of dropping fields.
        expected_entry = cleared | {"channel": cleared["channel"] | {"modulator": [1.0] * m}}
        c.require(snapshots["before_gate"] == expected_entry, "Wrong gate-entry boundary")
        for label in ("after_gate", "before_transfer"):
            expected_physical = before["physical"] | {
                "voltage_V": [
                    v + (1e-25 if label == "before_transfer" else 0.0)
                    for v in before["physical"]["voltage_V"]
                ]
            }
            expected_channel = expected_entry["channel"] | {
                key: post[key] for key in ("m", "h", "P", "derived_m_times_h")
            }
            c.require(
                snapshots[label]
                == {
                    "physical": expected_physical,
                    "channel": expected_channel,
                    "network_current": cleared["network_current"],
                },
                "Gate/transfer boundary differs from source-defined state changes",
            )
    else:
        c.require(row["observer"] is None, "Unexpected observation in control partner")


def case_metrics(r, row, prep, ledger, prefix):
    remix.moving_ions(row["primed_numeric_inventory"])
    plan = r["plan"]
    h, step, condition, query, mode = (
        row[k] for k in ("history", "dt_s", "condition", "query_index", "mode")
    )
    data = r["data"][h]
    c.require(
        h in plan["histories"]
        and step in plan["native_steps_s"]
        and condition in plan["conditions"]
        and mode in plan["modes"]
        and type(query) is int
        and 0 <= query < 3,
        "Unregistered native case",
    )
    c.require(
        row["single_updates"] == 2
        and row["initialization_seed"]
        == data["preparation_registration"]["transport_protocol"]["seed"]
        and row["actual_elapsed_single_updates_s"] == 2 * step
        and row["full_simulator_loop_executed"] is False
        and row["protocol_query_time_is_simulated_elapsed_time"] is False
        and row["hook_restored"] is True,
        "Native preflight scope or elapsed time changed",
    )
    c.require(
        row["initial"] == data["saved_initial"][f"{step:.8g}"]
        and row["initial_metadata"] == data["saved_metadata"][f"{step:.8g}"],
        "Native initial state/identity changed",
    )
    fixture = row["fixture"]
    c.require(
        fixture["applications"] == 1
        and fixture["declared_gate"] == data["initial_gate"]
        and fixture["metadata"] == row["initial_metadata"],
        "Initial gate fixture changed",
    )
    c.require(
        fixture["before"]["physical"] == fixture["after"]["physical"]
        and fixture["before"]["network_current"] == fixture["after"]["network_current"],
        "Initial fixture moved physical state",
    )
    for name, value in zip(("m", "h"), data["initial_gate"], strict=True):
        c.require(
            fixture["after"]["channel"][name] == [value] * prep["geometry"]["membrane_count"],
            "Initial fixture did not apply the declared gates",
        )
    c.require(row["prime"]["before"] == row["initial"], "Priming begins at wrong state")
    primed = row["prime"]["after_voltage"]
    c.require(
        primed["physical"]["inside_mM"] != row["initial"]["physical"]["inside_mM"]
        and any(primed["channel"]["density_mol_per_m2_s"]),
        "Missing nonzero native priming history",
    )
    physics = data["preparation_registration"]["transport_protocol"]
    baseline = physics["thickness_m"] * physics["max_permeability_m_per_s"] * physics["abundance"]
    c.require(
        row["initial_metadata"]["channel"]["maxDm_m2_per_s"] == baseline, "Wrong immutable baseline"
    )
    weights = [row["smooth_weight_mem"], row["smooth_weight_other"]]
    step_metrics(
        prefix + "/prime",
        row["prime"],
        prep["geometry"],
        physics,
        step,
        baseline,
        weights,
        mode,
        ledger,
    )
    inventory_link(row["primed_numeric_inventory"], primed)
    c.require(len(row["applications"]) == query + 1, "Missing or extra input applications")
    previous = baseline
    for index, app in enumerate(row["applications"]):
        time = plan["protocol_query_times_s"][index]
        expected_u = (
            0.0
            if condition == "static_blocked" or (condition == "suppression_release" and index == 1)
            else 1.0
        )
        c.require(
            app["protocol_query_s"] == time
            and app["candidate_step_index"] == round(time / step)
            and app["candidate_native_label_s"] == prep["candidate_labels_s"][round(time / step)]
            and app["actual_completed_single_updates"] == 1
            and app["integration_between_applications"] is False
            and app["availability"] == expected_u
            and app["baseline_maxDm_m2_per_s"] == baseline
            and app["previous_maxDm_m2_per_s"] == previous
            and app["applied_maxDm_m2_per_s"] == baseline * expected_u,
            "Input clock, baseline restoration or availability changed",
        )
        previous = app["applied_maxDm_m2_per_s"]
        c.require(
            app["before"] == app["after"] == primed
            and app["numeric_inventory_after"] == row["primed_numeric_inventory"],
            "Input mutated native state or numeric metadata",
        )
        fresh = app["fresh"]
        c.require(
            fresh["source"] == "betse.science.sim_toolbox.electroflux"
            and fresh["evaluation"] == "copied_pre_update_state_new_input_not_interval_current",
            "Wrong fresh/interval semantics",
        )
        expected_inputs = {
            "voltage_V": primed["physical"]["voltage_V"],
            "inside_K_mM": [
                primed["physical"]["inside_mM"][1][owner]
                for owner in prep["geometry"]["membrane_owners"]
            ],
            "outside_K_mM": primed["physical"]["outside_mM"][1],
            "valence": [1.0] * prep["geometry"]["membrane_count"],
            "diffusivity_m2_per_s": [
                a * b * previous
                for a, b in zip(primed["channel"]["m"], primed["channel"]["h"], strict=True)
            ],
        }
        c.require(
            fresh["inputs"] == expected_inputs,
            "Fresh probe did not use copied state and new parameter",
        )
        c.require(
            fresh["voltage_after_V"] == [v + 1e-25 for v in expected_inputs["voltage_V"]]
            and fresh["valence_after"] == [z + 1e-25 for z in expected_inputs["valence"]],
            "Copied electroflux argument side effects differ from pinned native source",
        )
        predicted = [
            float(
                ind.inward_density(
                    v,
                    ci,
                    co,
                    diffusion / physics["thickness_m"],
                    physics["constants"],
                    physics["temperature_K"],
                )
            )
            for v, ci, co, diffusion in zip(
                expected_inputs["voltage_V"],
                expected_inputs["inside_K_mM"],
                expected_inputs["outside_K_mM"],
                expected_inputs["diffusivity_m2_per_s"],
                strict=True,
            )
        ]
        ledger.add(
            f"{prefix}/input/{index}/fresh",
            fresh["density_mol_per_m2_s"],
            predicted,
            "density_mol_per_m2_s",
        )
        if not expected_u:
            zero(fresh["density_mol_per_m2_s"])
    c.require(
        row["probe"]["before"] == primed and row["final"] == row["probe"]["after_voltage"],
        "Probe state continuity differs",
    )
    expected_metadata = dict(row["initial_metadata"]) | {
        "channel": dict(row["initial_metadata"]["channel"]) | {"maxDm_m2_per_s": previous}
    }
    c.require(row["final_metadata"] == expected_metadata, "Input changed other native metadata")
    step_metrics(
        prefix + "/probe",
        row["probe"],
        prep["geometry"],
        physics,
        step,
        previous,
        weights,
        mode,
        ledger,
    )


def preparation_artifacts(r, output, group, prep):
    h, grid = group.split("/")
    data, step = r["data"][h], prep["dt_s"]
    c.require(
        step in r["plan"]["native_steps_s"]
        and grid == f"dt_{step:.8g}"
        and prep["geometry"] == data["geometry"]
        and prep["settings"] == data["settings"]
        and prep["source_constants"] == {"F": 96485.0, "R": 8.314},
        "Preparation identity differs",
    )
    ind.geometry_contract(prep["geometry"])
    c.require(
        prep["candidate_labels_s"] == data["saved_labels"][f"{step:.8g}"]
        and prep["candidate_steps"] == len(prep["candidate_labels_s"])
        and prep["labels_origin"]
        == "actual_Parameters_numpy_linspace_matches_saved_FULL_loop_not_new_loop",
        "Native candidate clock differs",
    )
    directory = output / "native" / group
    c.require(
        c.read(directory / "preparation.json") == prep
        and c.sha(directory / "native.yaml") == prep["native_yaml_sha256"],
        "Preparation artifacts differ",
    )


def case_artifacts(directory, row):
    initial_keys = {
        "history",
        "condition",
        "query_index",
        "mode",
        "dt_s",
        "initialization_seed",
        "fixture",
        "initial",
        "initial_metadata",
    }
    for filename, keys in (
        ("initial.json.gz", initial_keys),
        (
            "input-applied.json.gz",
            initial_keys | {"prime", "primed_numeric_inventory", "applications"},
        ),
    ):
        c.require(
            io.read_compressed(directory / filename) == {k: row[k] for k in keys},
            "Saved native boundary artifact differs: " + filename,
        )
    c.require(c.read(directory / "fixture.json") == row["fixture"], "Saved fixture differs")


def check(r, output, native):
    ctx.validate_plan(r["plan"])
    plan = r["plan"]
    physics = r["data"]["a"]["preparation_registration"]["transport_protocol"]
    ledger = Ledger(physics["tolerances"])
    c.require(native["test_only_subset"] is False, "Software subset cannot qualify full preflight")
    expected = {
        f"{h}/dt_{dt:.8g}/{condition}/query_{query}"
        for h in plan["histories"]
        for dt in plan["native_steps_s"]
        for condition in plan["conditions"]
        for query in range(3)
    }
    c.require(set(native["records"]) == expected, "Native case coverage differs")
    groups = {f"{h}/dt_{dt:.8g}" for h in plan["histories"] for dt in plan["native_steps_s"]}
    c.require(set(native["preparations"]) == groups, "Preparation group coverage differs")
    for group in sorted(groups):
        preparation_artifacts(r, output, group, native["preparations"][group])
    c.require(
        all(
            native[k] == plan[k]
            for k in ("geometry_seeds", "fresh_phases", "single_updates", "observer_pairs")
        ),
        "Wrong native execution counts",
    )
    starts, baselines, applications = {}, {}, 0
    for key in sorted(expected):
        h, grid, condition, query_name = key.split("/")
        group = h + "/" + grid
        prep = native["preparations"][group]
        c.require(set(native["records"][key]) == set(plan["modes"]), "Native mode coverage differs")
        pair = {}
        for mode in plan["modes"]:
            path = f"native/{key}/{mode}/result.json.gz"
            c.require(native["records"][key][mode] == path, "Unexpected native record path")
            row = io.read_compressed(output / path)
            print(f"Checking saved native case: {key}/{mode}", flush=True)
            c.require(
                row["history"] == h
                and grid == f"dt_{row['dt_s']:.8g}"
                and row["condition"] == condition
                and query_name == f"query_{row['query_index']}"
                and row["mode"] == mode,
                "Record/identity mismatch",
            )
            case_artifacts((output / path).parent, row)
            case_metrics(r, row, prep, ledger, key + "/" + mode)
            applications += len(row["applications"])
            start = row["prime"]["after_voltage"]
            if group in starts:
                c.require(starts[group] == start, "Different priming state between input cases")
            starts[group] = start
            pair[mode] = row
        a, b = pair["observed"], pair["unobserved"]

        # Keep comparison model-free: strip only observation fields and mode.
        def stripped(row):
            return {
                k: (
                    {n: v for n, v in value.items() if n != "observer"}
                    if k in ("prime", "probe")
                    else value
                )
                for k, value in row.items()
                if k != "mode"
            }

        c.require(stripped(a) == stripped(b), "Observer interfered with native physics")
        if condition == "baseline":
            baselines[(group, query_name)] = a["final"]
        elif condition == "no_op":
            c.require(a["final"] == baselines[(group, query_name)], "No-op input changed response")
    c.require(applications == plan["input_applications"] == 288, "Input application count differs")
    return ledger.summary() | {
        "failures": ledger.failures,
        "input_applications": applications,
        "zero_flux_mean_evidence": ledger.remix_records,
        "zero_flux_remixing": remix.summary(ledger.remix_records),
        "original_guard_rejections": ledger.original_guard_rejections,
        "observer_pairs": len(expected),
        "fresh_phases": 144,
        "single_updates": 288,
        "full_simulator_loop_executed": False,
        "release_response_qualified": False,
        "native_restart_qualified": False,
        "biology_validated": False,
        "gpu_tested": False,
    }
