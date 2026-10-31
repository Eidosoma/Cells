"""Manufactured deletion-prefix data only; no mesh, model or fixture execution in prep."""

import numpy as np

CASES = (
    "one_cell",
    "two_cells",
    "no_cells",
    "all_cells",
    "selector_order",
    "global_length_collision",
)
RAW_CASES = (
    "list_last_index",
    "empty_list_index",
    "nested_unknown_first",
    "nested_unknown_late",
    "scalar_array",
    "species_grid_collision",
    "alias_list_mutation",
    "duplicate_list_removal",
)
DEPENDENCIES = (
    "missing_geometry",
    "complete_metadata_is_not_checkpoint",
    "wrong_target_cells",
    "wrong_target_membranes",
    "malformed_parent_epoch",
    "changed_trial",
    "changed_epoch",
    "wrong_rebind_order",
    "wrong_rebind_parent",
    "missing_rebind_artifact",
    "legacy_ER_requested",
)


def fixture(case="one_cell"):
    if case not in CASES + RAW_CASES:
        raise ValueError("Choose a declared source deletion-prefix condition")
    n = 2 if case == "species_grid_collision" else 4
    m, e = 3 * n, 9
    owner = np.repeat(np.arange(n), 3)
    cell_ids = ["cell_" + str(i) for i in range(n)]
    mem_ids = ["mem_" + str(i) for i in range(m)]
    selected = [1]
    if case == "two_cells":
        selected = [0, 2]
    elif case in ("no_cells", "empty_list_index"):
        selected = []
    elif case == "all_cells":
        selected = list(range(n))
    elif case == "selector_order":
        selected = [2, 0]
    elif case == "list_last_index":
        selected = [n - 1]
    elif case == "duplicate_list_removal":
        selected = [n - 1, n - 1]
    targets = np.asarray(selected, np.int64)
    membranes = np.asarray([3 * cell + j for cell in selected for j in range(3)], np.int64)
    cell_to_mems = np.empty(n, dtype=object)
    for i in range(n):
        cell_to_mems[i] = list(range(3 * i, 3 * i + 3))
    cell_nn = [([i - 1] if i else []) + ([i] if i < n - 1 else []) for i in range(n)]
    cell_to_nn = np.empty(n, dtype=object)
    for i, row in enumerate(cell_nn):
        cell_to_nn[i] = row
    centres = np.asarray([[float(i) * 2e-6, 0.0] for i in range(n)])
    polygons = np.asarray(
        [
            [[float(i) * 2e-6, 0.0], [float(i) * 2e-6 + 1e-6, 0.0], [float(i) * 2e-6, 1e-6]]
            for i in range(n)
        ],
        dtype=object,
    )
    cells = dict(
        cell_i=np.arange(n),
        mem_i=np.arange(m),
        cell_to_nn_full=cell_to_nn,
        cell_to_mems=cell_to_mems,
        map_cell2ecm=np.arange(n),
        map_mem2ecm=np.arange(m) % e,
        cell_centres=centres,
        ecm_verts=polygons,
    )
    sim = dict(
        cdl=n,
        mdl=m,
        edl=e,
        cc_cells=np.arange(2 * n, dtype=float).reshape(2, n) + 1,
        cc_at_mem=np.arange(2 * m, dtype=float).reshape(2, m) + 1,
        cc_env=np.arange(2 * e, dtype=float).reshape(2, e) + 10,
        Dm_base=np.full((2, m), 1e-9),
        Dm_cells=np.full((2, m), 2e-9),
        Dm_scheduled=np.full((2, m), 1e-9),
        D_env=np.full((2, e), 1e-9),
        vm=np.arange(m, dtype=float) * 1e-3,
        cell_marker=np.arange(n, dtype=float),
        global_marker=np.array([101.0, 102.0, 103.0]),
        history=dict(previous=np.arange(m, dtype=float)),
        endo_retic=None,
    )
    if case == "global_length_collision":
        sim["global_marker"] = np.arange(n, dtype=float) + 100
    elif case in ("list_last_index", "empty_list_index", "duplicate_list_removal"):
        sim["witness_list"] = list(range(n))
    elif case == "nested_unknown_first":
        sim = dict(cc_mems=[np.arange(n + 1, dtype=float)], **sim)
    elif case == "nested_unknown_late":
        sim["cc_mems"] = [np.arange(n + 1, dtype=float)]
    elif case == "scalar_array":
        sim["scalar_bad"] = np.array(1.0)
    elif case == "alias_list_mutation":
        shared = list(range(n))
        sim["alias_first"] = shared
        sim["alias_second"] = shared
    topology = dict(
        cell_ids=cell_ids,
        membrane_ids=mem_ids,
        edge_ids=["contact_" + str(i) for i in range(n - 1)],
        environment_ids=["env_" + str(i) for i in range(e)],
        membrane_cell=owner.tolist(),
        membrane_environment=cells["map_mem2ecm"].tolist(),
        edge_cells=[[i, i + 1] for i in range(n - 1)],
        edge_membranes=[[3 * i + 1, 3 * (i + 1)] for i in range(n - 1)],
        edge_is_contact=[True] * (n - 1),
    )
    return dict(
        case_id=case,
        source=dict(
            simulator_fields=sim,
            cell_fields=cells,
            selection=dict(
                cells=targets,
                membranes=membranes,
                provenance=(
                    "Explicit supplied native picker return; no selector/RNG history inferred"
                ),
            ),
            parameters=dict(is_ecm=True, Ca_dyn=False),
            handler_fields={},
        ),
        topology=topology,
        removed_cell_ids=[cell_ids[i] for i in selected],
        field_declarations=dict(
            cell_amount=dict(
                values=np.arange(n, dtype=float) * 1e-9 + 1e-9,
                domain="cell",
                axis=0,
                kind="quantity",
                units="mol",
                quantity_units="mol",
            ),
            membrane_state=dict(
                values=sim["vm"].copy(), domain="membrane", axis=0, kind="state", units="V"
            ),
            global_grid=dict(
                values=sim["cc_env"].copy(),
                domain="global",
                axis=None,
                kind="state",
                units="mol/m3",
            ),
        ),
        physical_geometry_declared=False,
        whole_native_cut_claim=False,
    )
