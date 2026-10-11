"""Deterministic graph probe construction, with seed/prepared origins kept apart."""

import copy

import numpy as np

from scripts import check_e02_protocol as protocol_check
from tests import reference_source_graph as graph

ROOT = graph.eq.ROOT
DEFINITION = ROOT / "configs/reference/source_emt_graph_probes_v1.json"
DEFINITION_SHA256 = "f9f5ebbdb6e0ac499224d7d7be63d0d620612642900d987540abc3b0c10b0ad5"


def definition():
    return protocol_check.pinned_json(DEFINITION, DEFINITION_SHA256)


def make_case(name, cell_ids, edges, primary, context, *, origin, panel):
    n, e = len(cell_ids), len(edges)
    return {
        "id": name,
        "origin": origin,
        "cell_ids": list(cell_ids),
        "edge_ids": [10 * (i + 1) for i in range(e)],
        "edges": copy.deepcopy(edges),
        "primary": np.asarray(primary).tolist(),
        "context": np.asarray(context).tolist(),
        "membrane_diffusion": [[1e-18] * n for _ in range(3)],
        "ionic_diffusion": [[v] * e for v in panel["junction_ion_diffusion"]],
        "mirna_diffusion": [panel["junction_mirna_diffusion"]] * e,
        "gates": [None] * e,
        "swap_hemichannels": [False] * e,
        "controls": {
            "leak": [[1.0] * n for _ in range(3)],
            "pump": [1.0] * n,
            "ion_contact": [1.0] * e,
            "mirna_contact": [1.0] * e,
        },
    }


def permute(case, *, cells=None, edges=None):
    result = copy.deepcopy(case)
    if cells is not None:
        if sorted(cells) != list(range(len(case["cell_ids"]))):
            raise ValueError("Invalid cell permutation")
        result["cell_ids"] = [case["cell_ids"][i] for i in cells]
        for name in ("primary", "context", "membrane_diffusion"):
            result[name] = np.asarray(case[name])[:, cells].tolist()
        result["controls"]["leak"] = np.asarray(case["controls"]["leak"])[:, cells].tolist()
        result["controls"]["pump"] = [case["controls"]["pump"][i] for i in cells]
    if edges is not None:
        if sorted(edges) != list(range(len(case["edge_ids"]))):
            raise ValueError("Invalid edge permutation")
        for name in ("edge_ids", "edges", "mirna_diffusion", "gates", "swap_hemichannels"):
            result[name] = [case[name][i] for i in edges]
        result["ionic_diffusion"] = np.asarray(case["ionic_diffusion"])[:, edges].tolist()
        for name in ("ion_contact", "mirna_contact"):
            result["controls"][name] = [case["controls"][name][i] for i in edges]
    return result


def cases():
    data = definition()
    protocol = protocol_check.load_protocol()
    panel = protocol_check.pinned_json(graph.eq.PANEL, data["pair_panel_sha256"])
    if data["e02_protocol_sha256"] != protocol_check.PROTOCOL_SHA256:
        raise ValueError("E02 source freeze changed")
    if data["source_revision"] != panel["source_revision"] or data["schema_version"] != 1:
        raise ValueError("Graph probe identity differs")
    output = []
    if data["include_pair_initial_control_settings"]:
        for case in panel["cases"]:
            for time in [0.0, *[event["time"] for event in case.get("events", [])]]:
                output.append(graph.from_pair(panel, case, time).case)
    prep = protocol["preparation"]
    if data["include_e02_constructed_seed_conditions"]:
        for inventory in protocol_check.case_inventory():
            labels = inventory["prepared_labels"]
            # These are declared construction seeds, NOT future 500-unit packets.
            primary = np.array(
                [prep["initial_ions"] + prep["initial_regulation"][s] for s in labels]
            ).T
            context = np.array(
                [[prep["context"][name] for name in graph.eq.CONTEXT]] * len(labels)
            ).T
            case = make_case(
                f"seed/{inventory['id']}",
                inventory["cell_ids"],
                inventory["edges"],
                primary,
                context,
                origin="E02_constructed_seeds_not_prepared",
                panel=panel,
            )
            for name in ("membrane_diffusion", "ionic_diffusion", "mirna_diffusion"):
                case[name] = inventory[name]
            for name in ("ion_contact", "mirna_contact"):
                case["controls"][name] = inventory[name]
            output.append(case)
    if data["include_isolated_preparation_seeds"]:
        for label in ("E", "M"):
            output.append(
                make_case(
                    f"prepare_seed/{label}",
                    [100],
                    [],
                    np.array(prep["initial_ions"] + prep["initial_regulation"][label])[:, None],
                    np.array([prep["context"][name] for name in graph.eq.CONTEXT])[:, None],
                    origin="E02_preparation_initial_seed_only",
                    panel=panel,
                )
            )
    constructed = {}
    population = data["constructed_population"]
    for description in data["constructed_cases"]:
        if "from" in description:
            case = copy.deepcopy(constructed[description["from"]])
        else:
            selection = [population["cell_ids"].index(i) for i in description["cells"]]
            case = make_case(
                description["id"],
                description["cells"],
                description["edges"],
                np.asarray(population["primary"])[:, selection],
                np.asarray(population["context"])[:, selection],
                origin="constructed_gradient_not_prepared",
                panel=panel,
            )
        case["id"] = description["id"]
        for name in ("membrane_diffusion", "gates", "swap_hemichannels"):
            if name in description:
                case[name] = copy.deepcopy(description[name])
        case["controls"].update(copy.deepcopy(description.get("controls", {})))
        if description.get("reverse_edges", False):
            case["edges"] = [edge[::-1] for edge in case["edges"]]
        if description.get("swap_all_hemichannels", False):
            case["swap_hemichannels"] = [not flag for flag in case["swap_hemichannels"]]
        case = permute(
            case,
            cells=description.get("cell_permutation"),
            edges=description.get("edge_permutation"),
        )
        graph.Model(case, panel)  # validate each complete expanded input before any native call
        constructed[case["id"]] = case
        output.append(case)
    if len({case["id"] for case in output}) != len(output):
        raise ValueError("Duplicate graph probe identity")
    return output
