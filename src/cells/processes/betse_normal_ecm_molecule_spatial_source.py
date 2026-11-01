# ruff: noqa: E731
"""Literal BETSE1.5.0 gradient_x/y/r factories; no lifecycle admission here.

Source copyright Alexis Pietak and Cecil Curry; see the pinned BETSE LICENSE.
Radial execution requires an original retained cells.centre owner, currently
absent from the headless phase. Neither a probe nor a derived mean supplies it.
"""

import numpy as np


def gradient_x(pc, cells, p):
    """
    Creates a spatial gradient along the x-axis from 0 to 1 over a patch
    of cells defined by indices.

    Parameters
    ----------
    pc                 Indices of membranes or cells
    cells              Instance of Cells module
    p                  Instance of parameters
    targs              Indices of targets within mem or cell inds to apply gradient

    Returns
    ---------
    fx
        Data values from 0 to 1 defining a gradient in the x-direciton. If
        p.is_ecm == True, length of fx is number of membranes, otherwise length
        of fx is equal to cell number.
    dynamics
        Null quantity corresponding to time dynamics.
    """
    if len(pc) == len(cells.mem_i):
        x_vals_o = cells.mem_mids_flat[:, 0]
    elif len(pc) == len(cells.cell_i):
        x_vals_o = cells.cell_centres[:, 0]
    min_grad = x_vals_o.min()
    x_vals = x_vals_o - min_grad
    x_vals = x_vals / x_vals.max()
    x_mid = 0.5 + p.gradient_x_properties["x-offset"]
    n = p.gradient_x_properties["exponent"]
    grad_slope = (x_vals / x_mid) ** n / (1 + (x_vals / x_mid) ** n)
    fx = grad_slope * p.gradient_x_properties["slope"] + p.gradient_x_properties["z-offset"]
    dynamics = lambda t: 1
    return (fx, dynamics)


def gradient_y(pc, cells, p):
    """
    Creates a spatial gradient along the y-axis from 0 to 1 over a patch
    of cells defined by indices.

    If p.is_ecm is True, the data is defined and returned on membrane
    midpoints, otherwise cell centres are the defining structure.

    Parameters
    ----------
    pc                 Indices of membranes
    cells              Instance of Cells module
    p                  Instance of parameters

    Returns
    ---------
    fy
        Data values from 0 to 1 defining a gradient in the y-direciton. If
        p.is_ecm == True, length of fy is number of membranes, otherwise length
        of fy is equal to cell number.
    dynamics
        Null quantity corresponding to time dynamics.
    """
    if len(pc) == len(cells.mem_i):
        y_vals_o = cells.mem_mids_flat[:, 1]
    elif len(pc) == len(cells.cell_i):
        y_vals_o = cells.cell_centres[:, 1]
    min_grad = y_vals_o.min()
    y_vals = y_vals_o - min_grad
    y_vals = y_vals / y_vals.max()
    y_mid = 0.5 + p.gradient_y_properties["x-offset"]
    n = p.gradient_y_properties["exponent"]
    grad_slope = (y_vals / y_mid) ** n / (1 + (y_vals / y_mid) ** n)
    fy = grad_slope * p.gradient_y_properties["slope"] + p.gradient_y_properties["z-offset"]
    dynamics = lambda t: 1
    return (fy, dynamics)


def gradient_r(pc, cells, p):
    """
    Creates a spatial gradient in a radial direction from 0 to 1 over a patch
    of cells defined by indices.

    If p.is_ecm is True, the data is defined and returned on membrane
    midpoints, otherwise cell centres are the defining structure.

    Parameters
    ----------
    pc                 Indices of membranes
    cells              Instance of Cells module
    p                  Instance of parameters

    Returns
    ---------
    r
        Data values from 0 to 1 defining a gradient in the radial direction.  If
        p.is_ecm == True, length of r is number of membranes, otherwise length
        of r is equal to cell number.
    """
    fx = np.zeros(len(cells.mem_i))
    fy = np.zeros(len(cells.mem_i))
    fx[pc] = cells.mem_mids_flat[pc, 0] - cells.centre[0] - p.gradient_r_properties["x-offset"]
    fy[pc] = cells.mem_mids_flat[pc, 1] - cells.centre[1] - p.gradient_r_properties["x-offset"]
    r = np.sqrt(fx**2 + fy**2)
    r = r / r.max()
    r = r * p.gradient_r_properties["slope"] + p.gradient_r_properties["z-offset"]
    dynamics = lambda t: 1
    return (r, dynamics)
