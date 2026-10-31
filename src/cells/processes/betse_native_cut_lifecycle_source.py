# ruff: noqa: B007, B905, E721
"""Literal native deletion prefix; stops before the first DEC mesh mutation.

No geometry regeneration, solver continuation or complete native-cut claim.
"""

import copy
from types import SimpleNamespace

import numpy as np

logs = SimpleNamespace(log_info=lambda *_: None)


def flatten(ls_of_ls):
    ls_flat = []
    ind_map = []
    rind_map = copy.deepcopy(ls_of_ls)
    for i, sublist in enumerate(ls_of_ls):
        for j, val in enumerate(sublist):
            ls_flat.append(val)
            ind_map.append([i, j])
    for j, vals in enumerate(ind_map):
        rind_map[vals[0]][vals[1]] = j
    return (ls_flat, ind_map, rind_map)


tb = SimpleNamespace(flatten=flatten)


def deletion_prefix(self, phase, tissue_picker):
    cells = phase.cells
    p = phase.p
    sim = phase.sim
    target_inds_cell, target_inds_mem = tissue_picker.pick_cells_and_mems(cells=cells, p=p)
    target_inds_gj, _, _ = tb.flatten(cells.cell_to_nn_full[target_inds_cell])
    if p.is_ecm:
        ecm_targs_cell = list(cells.map_cell2ecm[target_inds_cell])
        ecm_targs_mem = list(cells.map_mem2ecm[target_inds_mem])
        ecm_targs = []
        for v in ecm_targs_cell:
            ecm_targs.append(v)
        for v in ecm_targs_mem:
            ecm_targs.append(v)
    hurt_cells = np.zeros(len(cells.cell_i))
    target_inds_gj_unique = np.unique(target_inds_gj)
    for i, inds in enumerate(cells.cell_to_nn_full):
        inds_array = np.asarray(inds)
        inds_in_target = np.intersect1d(inds_array, target_inds_gj_unique)
        if len(inds_in_target):
            hurt_cells[i] = 1
    hurt_inds = (hurt_cells == 1).nonzero()
    sim.hurt_mask = np.zeros(sim.cdl)
    sim.hurt_mask[hurt_inds] = 1.0
    sim_names = list(sim.__dict__.keys())
    specials_list = [
        "cc_cells",
        "cc_mems",
        "cc_env",
        "cc_er",
        "z_array",
        "z_array_er",
        "fluxes_gj",
        "fluxes_mem",
        "Dm_base",
        "Dm_cells",
        "Dm_scheduled",
        "Dm_vg",
        "Dm_cag",
        "Dm_morpho",
        "Dm_er_base",
        "Dm_er_CICR",
        "Dm_stretch",
        "Dm_custom",
        "D_gj",
        "fluxes_intra",
        "cc_at_mem",
    ]
    if p.is_ecm:
        specials_list.remove("cc_env")
        extra = ["z_array_cells"]
        for ent in extra:
            specials_list.append(ent)
    special_names = set(specials_list)
    for name in sim_names:
        if name in special_names:
            super_data = getattr(sim, name)
            super_data2 = []
            for i, data in enumerate(super_data):
                if isinstance(data, np.ndarray):
                    if len(data) == len(cells.cell_i):
                        data2 = np.delete(data, target_inds_cell)
                    elif len(data) == len(cells.mem_i):
                        data2 = np.delete(data, target_inds_mem)
                elif isinstance(data, list):
                    data2 = []
                    if len(data) == len(cells.cell_i):
                        for index in sorted(target_inds_cell, reverse=True):
                            del data[index]
                        data2.append(data[index])
                    elif len(data) == len(cells.mem_i):
                        for index in sorted(target_inds_mem, reverse=True):
                            del data[index]
                        data2.append(data[index])
                super_data2.append(data2)
            if type(super_data) == np.ndarray:
                super_data2 = np.asarray(super_data2)
            setattr(sim, name, super_data2)
        else:
            data = getattr(sim, name)
            if isinstance(data, np.ndarray):
                if len(data) == len(cells.cell_i):
                    data2 = np.delete(data, target_inds_cell)
                    setattr(sim, name, data2)
                elif len(data) == len(cells.mem_i):
                    data2 = np.delete(data, target_inds_mem)
                    setattr(sim, name, data2)
            elif isinstance(data, list):
                index = None
                data2 = []
                if len(data) == len(cells.cell_i):
                    for index in sorted(target_inds_cell, reverse=True):
                        del data[index]
                    data2.append(data[index])
                    setattr(sim, name, data2)
                elif len(data) == len(cells.mem_i):
                    for index in sorted(target_inds_mem, reverse=True):
                        del data[index]
                    data2.append(data[index])
                    setattr(sim, name, data2)
    if p.Ca_dyn and sim.endo_retic is not None:
        sim.endo_retic.remove_ers(sim, target_inds_cell)
    new_cell_centres = []
    new_ecm_verts = []
    removal_flags = np.zeros(len(cells.cell_i))
    removal_flags[target_inds_cell] = 1
    for i, flag in enumerate(removal_flags):
        if flag == 0:
            new_cell_centres.append(cells.cell_centres[i])
            new_ecm_verts.append(cells.ecm_verts[i])
    cells.cell_centres = np.asarray(new_cell_centres)
    cells.ecm_verts = np.asarray(new_ecm_verts, dtype=object)
    ecm_verts_flat, _, _ = tb.flatten(cells.ecm_verts)
    ecm_verts_set = set()
    for vert in ecm_verts_flat:
        ptx = vert[0]
        pty = vert[1]
        ecm_verts_set.add((ptx, pty))
    cells.ecm_verts_unique = [list(verts) for verts in list(ecm_verts_set)]
    cells.ecm_verts_unique = np.asarray(cells.ecm_verts_unique)
    logs.log_info("Recalculating cluster variables for new configuration...")
    return locals()
