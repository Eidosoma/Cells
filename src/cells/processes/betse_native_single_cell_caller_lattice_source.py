# Copyright 2014-2025 Alexis Pietak & Cecil Curry; see licenses/BETSE.txt.
"""Literal caller/lattice source; normalized scalar stores, no package/phase authority."""
from __future__ import annotations

from abc import ABCMeta
from enum import Enum

# Original source bodies and docstring values are retained verbatim in AST.
# ruff: noqa: E501,F821,F841,B007
# fmt: off

NATIVE_PINS = {'betse/science/cells.py': 'be38678a4f0bd084044fe7d952d74a4550003ce9701f5d073d1f124ba6daeaf2', 'betse/science/parameters.py': 'f36ec747918aa285ca043fe51086bcff4e4e2198cd4f30a138f1e58a51ecf85e', 'betse/util/type/types.py': '9b8c83555b06a18bfb252d236c95c0d625699237e5c5cc671c085d282fc2c089', 'betse/exceptions.py': 'c78612e009270a8d054ea6c52e9e7014ce22e0131a929530e7c3ddc318765971'}
SITES = {'Cells.__init__': 'c324faf842eb6667b294a9267c1b17d06c9a9be6cc4f6c688d2c2f917e838b3f', 'Cells._make_cell_lattice': '681709c00231ea0ba2fc9e4abb45d4dbe4ae9ea4350e912e8224447d872da50b', 'type_check': '3bfbdfbf80d99c105b711c15efe9a0d8caaf9a0857f2a0b3dd5a8e657c06968d', 'parameter_stores': '691e9a4a9a0114285280f382d248a6b3e66842375223e134bb58df0b87ccd3aa', 'BetseException': '1dd771616c87fe1f202d0a9b01a421ec1e5f8a36a72c6eef736a1e4b4790a7ef', 'BetseSimException': 'aa9cdbb28ffcad326a5543b5a14b6640fdb18bdc792ddf82be346a19b1bfa728', 'BetseSimConfException': '16cd59c8e586b9efbbfe1de6bcc5c3dc342803eb26daa183d13252e47591bed2'}

CellLatticeType = Enum("CellLatticeType", ("HEX", "SQUARE"))

def type_check(func: CallableTypes) -> CallableTypes:
    return func

class ParameterStores:
    def initialize_source_stores(self):
        self.wsx = self.world_len
        self.wsy = self.world_len
        self.ac = 1e-06
        self.d_cell = self.cell_radius * 2
        self.nx = int(self.wsx / self.d_cell)
        self.ny = int(self.wsy / self.d_cell)
        self.wsx = self.wsx + 5 * self.cell_lattice_disorder * self.d_cell
        self.wsy = self.wsy + 5 * self.cell_lattice_disorder * self.d_cell

class CellsKernel:

    @type_check
    def __init__(self, p: 'betse.science.parameters.Parameters') -> None:
        """
        Initialize this cell cluster with the passed simulation configuration.

        Parameters
        ----------
        p : betse.science.parameters.Parameters
            Current simulation configuration.
        """
        pass

    @type_check
    def _make_cell_lattice(self, p: 'betse.science.parameters.Parameters') -> None:
        """
        Create the randomly scattered lattice of **cell seed points** (i.e.,
        cell centres) defined on a 2D world space, with dimensions supplied by
        the :attr:`wsx` variable in meters.

        Specifically, this method defines the following object attributes:

        * ``xmin``, ``xmax``, ``ymin``, ``ymax``, the minimum and maximum points
          of the global world space.
        * ``centre``, the centre of the global world space.
        * ``clust_xy``, the list of `(x, y)` Cartesian coordinates of seed
          points.

        The amount of deviation from a square grid is specified by the
        :attr:`cell_lattice_disorder` variable, defined from 0 (perfect square
        grid) to 1 (full noise).

        Parameters
        -----------
        p : Parameters
            Current simulation configuration.
        """
        if p.cell_lattice_type is CellLatticeType.SQUARE:
            logs.log_info('Creating square cell lattice...')
            x_v = np.linspace(0, (p.nx - 1) * (p.d_cell + p.ac), p.nx)
            y_v = np.linspace(0, (p.ny - 1) * (p.d_cell + p.ac), p.ny)
            x_2d, y_2d = np.meshgrid(x_v, y_v)
            x_rnd = p.cell_lattice_disorder * p.d_cell * (np.random.rand(p.ny, p.nx) - 0.5)
            y_rnd = p.cell_lattice_disorder * p.d_cell * (np.random.rand(p.ny, p.nx) - 0.5)
            x_2d = x_2d + x_rnd
            y_2d = y_2d + y_rnd
            xypts = np.vstack((x_2d.ravel(), y_2d.ravel())).T
        elif p.cell_lattice_type is CellLatticeType.HEX:
            logs.log_info('Creating hexagonal cell lattice...')
            r = p.d_cell / 2
            a_hex = np.sqrt(3) * r
            b_hex = 3 * r
            blue_y_start = a_hex / 2
            blue_y_end = p.wsx - a_hex / 2
            blue_x_start = 0
            blue_x_end = p.wsy
            blue_space_y = a_hex
            blue_space_x = b_hex
            blue_x_num = int((blue_x_end - blue_x_start) / blue_space_x)
            blue_y_num = int((blue_y_end - blue_y_start) / blue_space_y)
            red_y_start = 0
            red_y_end = p.wsx
            red_x_start = b_hex / 2
            red_x_end = p.wsy - b_hex / 2
            red_space_y = a_hex
            red_space_x = b_hex
            red_x_num = int((red_x_end - red_x_start) / red_space_x)
            red_y_num = int((red_y_end - red_y_start) / red_space_y)
            x_blue = np.linspace(blue_x_start, blue_x_end, blue_x_num)
            y_blue = np.linspace(blue_y_start, blue_y_end, blue_y_num)
            x_red = np.linspace(red_x_start, red_x_end, red_x_num)
            y_red = np.linspace(red_y_start, red_y_end, red_y_num)
            x_2d_blue, y_2d_blue = np.meshgrid(x_blue, y_blue)
            x_2d_red, y_2d_red = np.meshgrid(x_red, y_red)
            x_2d = np.hstack((x_2d_blue.ravel(), x_2d_red.ravel()))
            y_2d = np.hstack((y_2d_blue.ravel(), y_2d_red.ravel()))
            x_rnd = p.cell_lattice_disorder * p.d_cell * (np.random.rand(len(x_2d)) - 0.5)
            y_rnd = p.cell_lattice_disorder * p.d_cell * (np.random.rand(len(y_2d)) - 0.5)
            x_2d = x_2d + x_rnd
            y_2d = y_2d + y_rnd
            xypts = np.vstack((x_2d, y_2d)).T
        else:
            raise BetseSimConfException('Cell lattice type "{}" unrecognized.'.format(p.cell_lattice_type))
        self.xmin = np.min(xypts[:, 0])
        self.xmax = np.max(xypts[:, 0])
        self.ymin = np.min(xypts[:, 1])
        self.ymax = np.max(xypts[:, 1])
        bbox = np.asarray([[self.xmin, self.ymin], [self.xmax, self.ymin], [self.xmax, self.ymax], [self.xmin, self.ymax]])
        self.centre = xypts.mean(axis=0)
        self.clust_xy = np.vstack((xypts, bbox))
        self.bbox = np.asarray([[self.xmin - p.cell_radius, self.ymin - p.cell_radius], [self.xmax + p.cell_radius, self.ymin - p.cell_radius], [self.xmax + p.cell_radius, self.ymax + p.cell_radius], [self.xmin - p.cell_radius, self.ymax + p.cell_radius]])
        self.xmin = self.xmin - p.cell_radius
        self.ymin = self.ymin - p.cell_radius
        self.xmax = self.xmax + p.cell_radius
        self.ymax = self.ymax + p.cell_radius
        self.xyaxis = [self.xmin, self.xmax, self.ymin, self.ymax]


class BetseException(Exception, metaclass=ABCMeta):
    """
    Abstract base class of all application-specific exceptions.
    """
    pass

class BetseSimException(BetseException):
    """
    General-purpose simulation exception.
    """
    pass

class BetseSimConfException(BetseSimException):
    """
    Simulation configuration-specific exception.
    """
    pass
