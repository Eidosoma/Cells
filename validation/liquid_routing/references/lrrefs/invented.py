"""`inputs_invented.json`: invented worlds in `inputs.json`'s schema, for the rehearsal of CRITERIA section 10.

None of the registered folder's volumes, flows, times or concentrations is used (a flow of exactly 0 in `inv-J0`, the one
labelled share and the site node's structure are roles, not values). Every world and run name has the prefix `inv-`
(Amendment 1, item 6), so the registered role is the name without it. Every node's throughput is at most 1 except in the
expected refusal, and kh of the default heat is at most 1/64 in every run, the expected stop's included (its lower well holds
a trace).
"""

import json

TRACE = 3e-12                      # mM; this folder's trace is 1e-12


def _constant(value):
    return [[0.0, value]]


def _world(volumes, start, outputs, end, inlets=None, links=(), faces=(), events=(), collectors=(), labels=None, sites=None,
           compare=None):
    block = {
        "collectors": list(collectors), "end_s": end, "events": list(events), "faces_pL_per_s": list(faces),
        "inlets_mM": inlets or {}, "labels": labels, "links_pL_per_s": list(links), "outputs_s": outputs, "sites": sites,
        "start_fmol": start, "temperature_K": 298.15, "volumes_pL": volumes}
    if compare is not None:
        block["compare_s"] = compare
    return block


def _run(arm, name, world, step, heat="exact", role="judged", variant=None, expects=None):
    return {"arm": arm, "expects": expects, "heat": heat, "name": name, "role": role, "step": {"s": step},
            "variant": variant, "world": world}


def _times(unit, count):
    return [unit * k for k in range(1, count + 1)]


def build():
    worlds, runs = {}, []

    # ---- arm 1: two wells, one step -----------------------------------------------------------------------------
    worlds["inv-eq-mid"] = _world({"1": 3.5, "2": 3.5}, {"T": {"1": 14.875, "2": 4.375}}, "one step", "one step",
                                  faces=[["1", "2", {"T": 0.328125}]])
    worlds["inv-eq-tr"] = _world({"1": 3.5, "2": 3.5}, {"T": {"1": 14.875, "2": 1.75e-11}}, "one step", "one step",
                                 faces=[["1", "2", {"T": 0.328125}]])
    worlds["inv-r4-mid"] = _world({"1": 1.75, "2": 8.75}, {"T": {"1": 9.1875, "2": 15.3125}}, "one step", "one step",
                                  faces=[["1", "2", {"T": 0.2734375}]])
    for world in ("inv-eq-mid", "inv-r4-mid"):
        for j, step in enumerate((1.25, 0.625, 0.3125, 0.15625)):
            runs.append(_run(1, f"{world} exact j={j}", world, step))
    for j, step in enumerate((0.078125, 0.0390625, 0.01953125, 0.009765625)):
        runs.append(_run(1, f"inv-eq-mid default j={j}", "inv-eq-mid", step, heat="default"))
    runs.append(_run(1, "inv-eq-tr default recorded", "inv-eq-tr", 0.0390625, heat="default", role="recorded"))

    # ---- arm 2: diffusion, an exchange, diffusion ------------------------------------------------------------------
    compare = _times(2.0625, 9)
    exchange = {"buffer_mM": {"T": 1.375}, "fraction": 0.375, "kind": "exchange", "node": "1", "time_s": 8.25}
    for name, events in (("inv-N-buffered", [exchange]), ("inv-N-none", [])):
        worlds[name] = _world({"1": 3.5, "2": 7.0}, {"T": {"1": 15.75, "2": 5.25}}, "every step", 18.5625,
                              faces=[["1", "2", {"T": 0.046875}]], events=events, compare=compare)
    runs.append(_run(2, "inv-eq-tr default stop", "inv-eq-tr", 0.078125, heat="default", role="expected stop",
                     expects={"kind": "check", "status": "refused"}))
    for heat in ("exact", "default"):
        for world in ("inv-N-buffered", "inv-N-none"):
            for j, step in enumerate((0.6875, 0.34375, 0.171875)):
                runs.append(_run(2, f"{world} {heat} j={j}", world, step, heat=heat))
    runs.append(_run(2, "inv-P8 event", "inv-N-buffered", 0.171875, role="plant", variant="event heat not booked"))

    # ---- arm 3: flows ----------------------------------------------------------------------------------------------
    unit = 1.03125
    outputs, end = _times(unit, 16), 16.5
    inlets = {"I": {"T": _constant(TRACE), "U": _constant(TRACE)}}
    q = 0.4375

    def chain(first, second):
        return [["I", first, _constant(q)], [first, second, _constant(q)], [second, "K", _constant(q)]]

    start = {"T": {"A": 11.375, "B": 1.05e-11}, "U": {"A": 1.05e-11, "B": 7.875}}
    equal = {"A": 3.5, "B": 3.5}
    worlds["inv-F1"] = _world(equal, start, outputs, end, inlets, chain("A", "B"), collectors=["K"])
    worlds["inv-F1L"] = _world(equal, start, outputs, end, inlets, chain("A", "B"), collectors=["K"],
                               labels={"base": "plain", "names": ["plain", "tag"], "species": "T",
                                       "start_shares": {"A": {"tag": 1.0}}})
    worlds["inv-F2"] = _world(equal, start, outputs, end, inlets, chain("B", "A"), collectors=["K"])
    worlds["inv-F3"] = _world({"A": 3.5, "B": 8.75}, {"T": {"A": 11.375, "B": 2.625e-11}, "U": {"A": 1.05e-11, "B": 7.875}},
                              outputs, end, inlets, chain("A", "B"), collectors=["K"])
    worlds["inv-F6"] = _world(
        {"A": 7.0, "B": 3.5, "C": 5.5},
        {"T": {"A": 11.375, "B": 1.05e-11, "C": 1.65e-11}, "U": {"A": 2.1e-11, "B": 7.875, "C": 1.65e-11}},
        outputs, end, inlets,
        [["I", "A", _constant(q)], ["A", "B", _constant(1.125)], ["B", "C", _constant(1.125)], ["C", "A", _constant(0.6875)],
         ["C", "K", _constant(q)]], collectors=["K"])
    worlds["inv-F7"] = _world(
        {"A": 3.5, "B": 3.5, "S": 1.5},
        {"L": {"A": 1.05e-11, "B": 1.05e-11, "S": 0.0033}, "T": {"A": 11.375, "B": 1.05e-11, "S": 4.5e-12},
         "U": {"A": 1.05e-11, "B": 7.875, "S": 4.5e-12}},
        outputs, end, {"I": {"L": _constant(TRACE), "T": _constant(TRACE), "U": _constant(TRACE)}}, chain("A", "B"),
        collectors=["K"],
        sites={"copies": 1806642.0, "k_off_per_s": 0.04, "k_on_per_mM_s": 8.0, "ligand": "L", "node": "S",
               "sites_per_copy": 1, "start_occupancy": 0.0})
    for world in ("inv-F1", "inv-F2", "inv-F3", "inv-F1L"):
        for step in (8.25, 1.03125, 0.12890625):
            runs.append(_run(3, f"{world} h={step!r}", world, step))
    for step in (1.03125, 0.12890625):
        runs.append(_run(3, f"inv-F6 h={step!r}", "inv-F6", step))
    runs.append(_run(3, "inv-F6 h=8.25 refused", "inv-F6", 8.25, role="expected refusal",
                     expects={"kind": "domain", "status": "refused"}))
    runs.append(_run(3, "inv-F7 h=1.03125", "inv-F7", 1.03125))
    runs.append(_run(3, "inv-F7 h=1.03125 no router", "inv-F7", 1.03125, role="support", variant="no router"))
    runs.append(_run(3, "inv-P8 flow", "inv-F1", 1.03125, role="plant", variant="flow heat not booked"))

    # ---- arm 4: the growing collector ----------------------------------------------------------------------------------
    worlds["inv-G1"] = _world(
        {}, {"T": {}}, _times(unit, 6), 6.1875, {"Px": {"T": _constant(1.75)}, "Py": {"T": _constant(3.5)}},
        events=[{"inlet": "Px", "kind": "delivery", "time_s": 2.0625, "to": "K", "volume_pL": 0.75},
                {"inlet": "Py", "kind": "delivery", "time_s": 4.125, "to": "K", "volume_pL": 1.25}], collectors=["K"])
    worlds["inv-G5"] = _world({}, {"T": {}}, _times(unit, 8), 8.25, {"I": {"T": [[0.0, 1.75], [4.125, 3.5]]}},
                              [["I", "K", _constant(0.375)]], collectors=["K"])
    runs.append(_run(4, "inv-G1 h=1.03125", "inv-G1", 1.03125))
    for step in (4.125, 1.03125, 0.12890625):
        runs.append(_run(4, f"inv-G5 h={step!r}", "inv-G5", step))
    runs.append(_run(4, "inv-G5 h=1.03125 restart", "inv-G5", 1.03125, role="support", variant="restart at 4.125 s"))

    # ---- arm 5: the heat of each holder ------------------------------------------------------------------------------------
    long_outputs = _times(2.0625, 8)
    unequal = {"A": 3.5, "B": 5.25}
    worlds["inv-H1"] = _world(unequal, {"T": {"A": 9.625, "B": 6.5625}}, long_outputs, end,
                              {"I": {"T": _constant(0.625)}}, chain("A", "B"), collectors=["K"])
    worlds["inv-H2"] = _world(equal, {"T": {"A": 9.625, "B": 7e-10}}, long_outputs, end, {"I": {"T": _constant(2e-10)}},
                              chain("A", "B"), collectors=["K"])
    worlds["inv-H5"] = _world(unequal, {"T": {"A": 3.0625, "B": 4.59375}, "U": {"A": 5.6875, "B": 8.53125}}, long_outputs, end,
                              {"I": {"T": _constant(0.875), "U": _constant(1.625)}}, chain("A", "B"), collectors=["K"])
    for world in ("inv-H1", "inv-H2"):
        for step in (0.2578125, 0.12890625, 0.064453125):
            runs.append(_run(5, f"{world} h={step!r}", world, step))
    runs.append(_run(5, "inv-H5 h=0.12890625", "inv-H5", 0.12890625))

    # ---- arm 6: a flow beside a face -------------------------------------------------------------------------------------------
    six_start = {"T": {"A": 9.625, "B": 6.5625}, "U": {"A": 6.125, "B": 3.28125}}
    six_inlets = {"I": {"T": _constant(0.375), "U": _constant(0.375)}}
    six_face = [["A", "B", {"T": 0.21875, "U": 0.0}]]
    worlds["inv-J1"] = _world(unequal, six_start, long_outputs, end, six_inlets, chain("A", "B"), six_face, collectors=["K"])
    worlds["inv-J0"] = _world(unequal, six_start, long_outputs, end, six_inlets,
                              [["I", "A", _constant(0.0)], ["A", "B", _constant(0.0)], ["B", "K", _constant(0.0)]], six_face,
                              collectors=["K"])
    for step in (0.515625, 0.2578125, 0.12890625):
        runs.append(_run(6, f"inv-J1 h={step!r}", "inv-J1", step))
    runs.append(_run(6, "inv-J0 h=0.2578125", "inv-J0", 0.2578125))
    runs.append(_run(6, "inv-J0 h=0.2578125 no router", "inv-J0", 0.2578125, role="support", variant="no router"))

    return {"placement": {"arm_7_pairs": [], "note": "invented worlds for the rehearsal of CRITERIA.md section 10; none is "
                          "registered", "z_def": 0.0146484375},
            "schema": "liquid-routing inputs, version 1", "runs": runs, "worlds": worlds}


def text():
    """The file's bytes: one line per run and per world, as the registered inputs file has them."""
    table = build()
    lines = ["{", f' "placement": {json.dumps(table["placement"], sort_keys=True)},',
             f' "schema": {json.dumps(table["schema"])},', ' "runs": [']
    runs = [f"  {json.dumps(run, sort_keys=True)}" for run in table["runs"]]
    lines.append(",\n".join(runs))
    lines.append(" ],")
    lines.append(' "worlds": {')
    worlds = [f"  {json.dumps(name)}: {json.dumps(block, sort_keys=True)}" for name, block in sorted(table["worlds"].items())]
    lines.append(",\n".join(worlds))
    lines.append(" }")
    lines.append("}")
    return "\n".join(lines) + "\n"
