# Copyright 2014-2025 Alexis Pietak & Cecil Curry; see licenses/BETSE.txt.
# ruff: noqa: E501, F821
"""Literal selected mapping/helper bodies; no package/decorator/field admission.

The supported NumPy type declarations retain the original Sequence/ndarray
identities. Whole optional-import/YAML/phase/package bootstrap is outside this
normalized method namespace. No geometry, operators, or masks are constructed.
"""

from abc import ABCMeta
from collections.abc import Sequence
from types import SimpleNamespace

import numpy as np
from scipy import interpolate as interp

# Original types.py supported-NumPy arm, lines727/732.
NumpyArrayType = np.ndarray
SequenceTypes = (Sequence, NumpyArrayType)
SOURCE_PINS = {
    "betse/science/cells.py": "be38678a4f0bd084044fe7d952d74a4550003ce9701f5d073d1f124ba6daeaf2",
    "betse/lib/numpy/nparray.py": "f7c1362a5c6daf545b6a516e0ce06fe53242c13abd05a5f2520226b7dd222889",
    "betse/util/type/iterable/sequences.py": "fbd68c0d532ad56d81e8a90696d95465cd21c78b46db28f34f939f74f412abb1",
    "betse/util/type/types.py": "9b8c83555b06a18bfb252d236c95c0d625699237e5c5cc671c085d282fc2c089",
    "betse/exceptions.py": "c78612e009270a8d054ea6c52e9e7014ce22e0131a929530e7c3ddc318765971",
}
NATIVE_LINES = {
    "map_cells_centre_to_grids_centre": (2825, 2854),
    "map_cells_centre_to_points": (2883, 3017),
    "from_iterable": (95, 148),
    "is_sequence": (242, 265),
}


class BetseException(Exception, metaclass=ABCMeta):
    """
    Abstract base class of all application-specific exceptions.
    """

    pass


class BetseTypeException(BetseException):
    """
    General-purpose exception applicable to all types (i.e., classes).
    """

    pass


class BetseIterableException(BetseTypeException):
    """
    Iterable-specific exception.
    """

    pass


class BetseSequenceException(BetseIterableException):
    """
    Sequence-specific exception.
    """

    pass


def from_iterable(iterable):
    """
    Convert the passed iterable into a Numpy array.

    If this iterable is:

    * A non-sequence (e.g., generator), this iterable is first converted into a
      sequence and finally into a Numpy array.
    * A non-Numpy sequence (e.g., :class:`list`), this sequence is directly
      converted into a Numpy array.
    * A Numpy array, this array is returned unmodified.

    Caveats
    -------
    **This high-level function should always be called in lieue of the
    :func:`np.asarray` function,** which is fundamentally unsafe and should
    *never* be called directly. Unlike this function, the :func:`np.asarray`
    function unsafely converts *any* arbitrary non-sequence into a Numpy array.
    This function safely wraps the unsafe :func:`np.asarray` function with type
    and sanity checking, preventing that function's overly permissive design
    imperatives from corrupting the fragile purity of this codebase: e.g.,

    .. code-block:: pycon

       >>> import numpy as np
       >>> np.asarray(None)
       array(None, dtype=object)
       >>> np.asarray(
       ...     'We are the Bug. '
       ...     'Your computational and technological distinctiveness '
       ...     'will be added to our own. Resistance is futile.'
       ... )
       array('We are the Bug. Your computational and technological distinctiveness will be added to our own. Resistance is futile.',
       dtype='<U116')

    Parameters
    ----------
    iterable : IterableTypes
        Iterable to be converted into a Numpy array.

    Returns
    -------
    NumpyArrayType
        Numpy array converted from this iterable.
    """
    sequence = iterable if sequences.is_sequence(iterable) else tuple(iterable)
    return np.asarray(sequence)


def is_sequence(*objs: object):
    """
    ``True`` only if all passed objects are **sequences** (i.e., of types
    conforming to but *not* necessarily subclassing the canonical
    :class:`collections.abc.Sequence` API).

    Parameters
    ----------
    objs : tuple[object]
        Tuple of all objects to be tested.

    Returns
    ----------
    bool
        ``True`` only if these objects are all sequences.

    See Also
    ----------
    :class:`collections.abc.Sequence`
        Further details.
    """
    return all((isinstance(obj, SequenceTypes) for obj in objs))


class CellMappings:
    def map_cells_centre_to_grids_centre(self, *args, **kwargs):
        """
        Convert the passed one- or two-dimensional sequence of arbitrary data
        spatially situated at cell centres into a Numpy array of the same
        dimensionality and data spatially situated at environmental (i.e.,
        extracellular) grid space centres.

        See Also
        -----------
        :meth:`map_cells_centre_to_points`
            Further details.
        """
        return self.map_cells_centre_to_points(
            *args, target_points=(self.X, self.Y), data_factor=self.maskECM, **kwargs
        )

    def map_cells_centre_to_points(
        self, cells_centre_data, target_points, interp_method="linear", data_factor=1
    ):
        """
        Convert the passed one- or two-dimensional sequence of arbitrary data
        spatially situated at cell centres into a Numpy array of the same
        dimensionality and data spatially situated at the passed target points.

        Parameters
        -----------
        cells_centre_data : SequenceTypes
            One- or two-dimensional sequence of length the number of cells such
            that each element is arbitrary cell data spatially situated at the
            centre of that cell.
        target_points : SequenceTypes
            Two-dimensional sequence of the coordinates of all target points to
            interpolate this cell data onto, whose:
            #. First dimension indexes first the X and then Y axis.
            #. Second dimension indexes each target point such that each element
               is the coordinate of that point along this axis.
            For each target point, the output data returned for source data
            defined at cells whose membranes overlap this target point is
            defined as follows:
            * If this target point resides *inside* the convex hull of this cell
              cluster, this output data is spatially interpolated from the
              centres of these cells onto this target point.
            * Else, 0. In this case, this target point resides *outside* the
              convex hull of this cell cluster. The source data is spatially
              situated at cell centres and hence perfectly intracellular. No
              extracellular source data exists with which to interpolate onto
              extracellular target points.
        interp_method : optional[str]
            Interpolation type to pass to the
            :func:`scipy.interpolate.gridddata` function (e.g., ``nearest``,
            ``linear``, ``cubic``). Defaults to ``linear``.
        data_factor : NumericOrSequenceTypes
            Integer, float, or one-dimensional sequence of integers or floats
            by which to multiply all elements of the returned array. Defaults to
            1, in which case this array is returned as is. Specifically, if this
            array is:
            * One-dimensional, this array itself is multiplied by this factor.
            * Two-dimensional, each element of the first dimension of this array
              is multiplied by this factor.

        Returns
        -----------
        ndarray
            One- or two-dimensional Numpy array of length the number of target
            points such that each element is arbitrary cell data spatially
            interpolated onto the nearast target point.
        """
        cells_centre_data = nparray.from_iterable(cells_centre_data)
        if len(cells_centre_data.shape) not in {1, 2}:
            raise BetseSequenceException(
                "Source data dimensionality {} neither one- nor two-dimensional.".format(
                    len(cells_centre_data.shape)
                )
            )
        if cells_centre_data.shape[-1] != self.cell_centres.shape[0]:
            raise BetseSequenceException(
                "Source data not spatially situated at cell centres (i.e., last dimension length {} not {}).".format(
                    cells_centre_data.shape[-1], self.cell_centres.shape[0]
                )
            )
        if len(target_points) != 2:
            raise BetseSequenceException(
                "Target points not coordinate pairs (i.e., first dimension length {} not 2).".format(
                    len(target_points)
                )
            )
        cell_centres = (self.cell_centres[:, 0], self.cell_centres[:, 1])
        griddate_kwargs = {
            "points": cell_centres,
            "xi": target_points,
            "method": interp_method,
            "fill_value": 0,
        }
        if len(cells_centre_data.shape) == 1:
            return data_factor * interp.griddata(values=cells_centre_data, **griddate_kwargs)
        else:
            cells_centre_data_interpolated = []
            for cells_centre_data_one in cells_centre_data:
                cells_centre_data_one_interpolated = data_factor * interp.griddata(
                    values=cells_centre_data_one, **griddate_kwargs
                )
                cells_centre_data_interpolated.append(cells_centre_data_one_interpolated)
            return nparray.from_iterable(cells_centre_data_interpolated)


sequences = SimpleNamespace(is_sequence=is_sequence)
nparray = SimpleNamespace(from_iterable=from_iterable)
