# Copyright 2014-2025 Alexis Pietak & Cecil Curry; see licenses/BETSE.txt.
"""Pinned literal image/caller source; no source work runs at import.

Private source helpers require per-execution filesystem/image namespaces.
These definitions grant no package, physical, checkpoint or caller admission.
"""
from __future__ import annotations

from abc import ABCMeta, abstractmethod
from enum import Enum
from os import path as os_path

import numpy as np
from numpy import array
from PIL import Image
from scipy.interpolate import RectBivariateSpline
from scipy.spatial import ConvexHull

# Original ASTs, docstrings and unused locals are retained.
# ruff: noqa: E501,F821,F841,B007,B905,E731
# fmt: off

NATIVE_PINS = {'betse/exceptions.py': 'c78612e009270a8d054ea6c52e9e7014ce22e0131a929530e7c3ddc318765971', 'betse/lib/numpy/nparray.py': 'f7c1362a5c6daf545b6a516e0ce06fe53242c13abd05a5f2520226b7dd222889', 'betse/lib/pil/pilnumpy.py': '0e0f9c7589c8ae0d41d59c0f8306db66f4d87086932e1c7d7bf9cbe340f631b4', 'betse/science/cells.py': 'be38678a4f0bd084044fe7d952d74a4550003ce9701f5d073d1f124ba6daeaf2', 'betse/science/tissue/picker/tispickcls.py': 'c1c592ddc600479806da73c37ade7aecf19df0f49cd46706a74ad6bb9f1bc773', 'betse/science/tissue/picker/tispickimage.py': '75c5252998e73cce4f94d8ee03de5c206a82fae6caa1f33d0ae53260cef4a1ac', 'betse/util/math/mathinterp.py': '15f3f217e151fbd9e01dff55d771d600e895b9585afc123f1ee54af2a166f4de', 'betse/util/path/dirs.py': 'c18337d0564727251cf5367cca094ad373148f159ca55317d3d64de8a2436d4a', 'betse/util/path/files.py': '5bb48c45c609fe7f161cc5062d6a5ab7a543409333cd004d225bb4cb605a4a66', 'betse/util/path/pathnames.py': '7530fe8e0deeb0806787859c01a0d1d4448457af8126d859ceb82594ea69969b', 'betse/util/path/paths.py': '4dd3c7aa0a9e9e973d556ecaea6b9dcf63ac9e248e1011560516d7f901521b4f', 'betse/util/type/types.py': '9b8c83555b06a18bfb252d236c95c0d625699237e5c5cc671c085d282fc2c089'}
SITES = {'type_check': {'ast_sha256': '3bfbdfbf80d99c105b711c15efe9a0d8caaf9a0857f2a0b3dd5a8e657c06968d', 'kind': 'full_ast'}, 'is_absolute': {'ast_sha256': '8b979603842e489ef55c39690e213e47cfeeaf5076d6b83c42740b4ee0717e10', 'kind': 'full_ast'}, 'is_relative': {'ast_sha256': '041f4fcf534bee52788cef3a4d561b1189e5eddd56de0902993972d856a69cc9', 'kind': 'full_ast'}, 'die_if_absolute': {'ast_sha256': '2cb6e423e980cc540664baeb6ab97d4f50e45d42e9f681d885bb608f112e80ab', 'kind': 'full_ast'}, 'join': {'ast_sha256': 'd1ec45165efed3d02759f53c5f6f009a430355864a380b29553c3cc8ad9a0610', 'kind': 'full_ast'}, 'get_basename': {'ast_sha256': 'e0e2f646b174066fa77032eaaa872e95c945b25826b67b449b836227c487626f', 'kind': 'full_ast'}, 'is_file': {'ast_sha256': '4c15577603de4fa5a43f62f48c70268b3ed6070625eb15da36bab09ea43e65c3', 'kind': 'full_ast'}, 'die_unless_file': {'ast_sha256': '591df2732703a193703275d8cb5a3d6c5ab5a19681f7c0803a7d18ca41f3fc96', 'kind': 'full_ast'}, 'is_dir': {'ast_sha256': 'adf13d5e6c86c645ac0d34b0b92c952c5295a752cdc1b9c8060b6754b302133a', 'kind': 'full_ast'}, 'is_path': {'ast_sha256': '41b8a5068e69f0df28fb99a2348740ecae37cf6ef6eeffa226b3b33872524f3b', 'kind': 'full_ast'}, 'to_signed': {'ast_sha256': '6d63ea6a7f104e2a13b62304e329e56c5ce868a2b2be02f3e8890d2c930ac511', 'kind': 'full_ast'}, 'load_image': {'ast_sha256': '1302713189fba98f63cfb9972d158988553ae3216475375331ae61b5845634d4', 'kind': 'full_ast'}, 'interp2d_linear': {'ast_sha256': 'b1a397166da01b9b1bb20de85b817c18afcb3ca4261086a2888968ee2c61e599', 'kind': 'full_ast'}, 'ImageModeType': {'ast_sha256': '99fe120d51b4926f9776dd5d9db169b00fa4784ae68157f0d532cf47ac9d282c', 'kind': 'full_ast'}, 'TissuePickerABC': {'ast_sha256': '531dddda894c4e863a831f657e8d325d6acc2b2e65ba7621c54f0477d96031c7', 'kind': 'full_ast'}, 'TissuePickerImageMask': {'ast_sha256': '55af1922d59ff4b10360e3632f7013b3a3d05e6f368854d8311c600ed23ea521', 'kind': 'full_ast'}, 'TissuePickerImage': {'ast_sha256': 'c0e87c73e62558f1be6fed0e7185ec3819b0260db3dddc897358c02e37f1cbc8', 'kind': 'full_ast'}, 'DTYPE_UNSIGNED_TO_SIGNED': {'ast_sha256': 'a7b04f89816efba48d69549c9c72536bc92d33b7e403b16baec0fa8e7307b849', 'kind': 'full_ast'}, 'BetseException': {'ast_sha256': '1dd771616c87fe1f202d0a9b01a421ec1e5f8a36a72c6eef736a1e4b4790a7ef', 'kind': 'full_ast'}, 'BetseMathException': {'ast_sha256': '9866c58c46cc8a343f15717036a2dbf7e916c8905614d984399749075a1e3b92', 'kind': 'full_ast'}, 'BetseMathInterpolationException': {'ast_sha256': 'd1ccdeacb39eeca6a10fa60d9f54bc9e21bec4a24d160d656ffbaf7564d55a45', 'kind': 'full_ast'}, 'BetsePathnameException': {'ast_sha256': 'a29b486753ebf3d284a490f92605e5fe128bfc9e08c3de05e00c107987ea17e0', 'kind': 'full_ast'}, 'BetsePathException': {'ast_sha256': 'bee66989bfa12cbd3be987e353ae343b932c6776ffa1883f966ebe0c22098bfa', 'kind': 'full_ast'}, 'BetseFileException': {'ast_sha256': '3ae41b273db6617b93b5e41c9ae56e9df1de4fa90d3993dfff34ba58e6c7a77b', 'kind': 'full_ast'}, 'BetseImageException': {'ast_sha256': '48af3ec4ebf9b5c37e13198f7415ef4cd066b4a66efa650a586008f4a48402cc', 'kind': 'full_ast'}, 'make_voronoi_mesh_aliases': {'ast_sha256': '1e7924ec8207280f2ff14347f9f67e4aee6bdb5155b124ce35c36da7c47d3cff', 'kind': 'body_ast'}, 'cell_index': {'ast_sha256': 'e8b10040895adc3875baaa9d67817e677290b585ef66866e7b59079491d0f369', 'kind': 'full_ast'}}

def type_check(func: CallableTypes) -> CallableTypes:
    return func

class BetseException(Exception, metaclass=ABCMeta):
    """
    Abstract base class of all application-specific exceptions.
    """
    pass

class BetseMathException(BetseException):
    """
    General-purpose exception applicable to all low-level math algorithms.
    """
    pass

class BetseMathInterpolationException(BetseMathException):
    """
    Interpolation-specific math exception.
    """
    pass

class BetsePathnameException(BetseException):
    """
    Pathname-specific exception.
    """
    pass

class BetsePathException(BetseException):
    """
    Path-specific exception.
    """
    pass

class BetseFileException(BetsePathException):
    """
    File-specific exception.
    """
    pass

class BetseImageException(BetseFileException):
    """
    Image file-specific exception.
    """
    pass
DTYPE_UNSIGNED_TO_SIGNED = {np.uint8: np.int16, np.uint16: np.int32, np.uint32: np.int64}

@type_check
def is_absolute(pathname: str) -> bool:
    """
    ``True`` only if the passed path is absolute.

    The definition of "absolute" depends on the current operating system.
    Specifically, under:

    * POSIX-compatible systems, absolute paths are prefixed by ``/``.
    * Microsoft Windows, absolute paths are prefixed by an optional drive
      indicator (e.g., ``C:``) followed by ``\\``.
    """
    return os_path.isabs(pathname)

def is_relative(pathname: str) -> bool:
    """
    ``True`` only if the passed path is relative.

    The definition of "relative" depends on the current operating system.
    Specifically, under:

    * POSIX-compatible systems, relative paths are *not* prefixed by ``/``.
    * Microsoft Windows, relative paths are *not* prefixed by an optional drive
      indicator (e.g., ``C:``) followed by ``\\``.
    """
    return not is_absolute(pathname)

def die_if_absolute(*pathnames: str) -> None:
    """
    Raise an exception if any passed pathname is absolute.

    Equivalently, this function raises an exception unless unless all passed
    pathnames are relative.

    Raises
    ----------
    BetsePathnameException
        If any such pathname is absolute.

    See Also
    ----------
    :func:`is_absolute`
        Further details.
    """
    for pathname in pathnames:
        if is_absolute(pathname):
            raise BetsePathnameException('Pathname "{}" absolute rather than relative.'.format(pathname))

@type_check
def join(*partnames: str) -> str:
    """
    Join (i.e., concatenate) the passed pathnames with the directory separator
    specific to the current platform.

    Caveats
    ----------
    This high-level wrapper should *always* be called in lieu of the low-level
    :func:`os.path.join` function, which sadly violates Python's core "Explicit
    is better than implicit." design principle. Specifically, to quote official
    :func:`os.path.join` documentation:

        If a component is an absolute path, all previous components are thrown
        away and joining continues from the absolute path component.

    Non-intuitive path mangling of that sort only promotes non-debuggable bugs.
    This function prevents these bugs by explicitly raising an exception if any
    passed pathname except the first is absolute.

    Parameters
    ----------
    partnames : tuple[str]
        Tuple of all pathnames to be joined. The first such pathname may be
        absolute or relative. All remaining pathnames *must* be relative.

    Returns
    ----------
    str
        Absolute or relative pathname joined from these pathnames.

    Raises
    ----------
    BetsePathnameException
        If any such pathname except the first is absolute.
    """
    if len(partnames) > 1:
        die_if_absolute(*partnames[1:])
    return os_path.join(*partnames)

@type_check
def get_basename(pathname: str) -> str:
    """
    **Basename** (i.e., last component) of the passed path.
    """
    return os_path.basename(pathname)

@type_check
def is_file(*pathnames: str) -> bool:
    """
    ``True`` only if all passed paths are existing non-directory files *after*
    following symbolic links.

    If any such path does *not* exist, this function silently ignores this path
    rather than raising an exception.

    Versus :func:`path.isfile`
    ----------
    This function intrinsically differs from the standard :func:`path.isfile`
    function. While the latter returns ``True`` only for non-special files and
    hence `False` for all non-directory special files (e.g., device nodes,
    sockets), this function returns ``True`` for *all* non-directory files
    regardless of whether these files are special or not.

    **Why?** Because this function complies with POSIX semantics, whereas
    :func:`path.isfile` does *not*. The specialness of non-directory files is
    usually irrelevant; in general, it only matters whether these files are
    directories or not. For example, the external ``rm`` command removes only
    non-directory files (regardless of specialness) while the external
    ``rmdir`` command removes only empty directories.

    Parameters
    ----------
    pathnames: tuple[str]
        Tuple of all paths to be tested.

    Returns
    ----------
    bool
        ``True`` only if all such paths are existing non-directory files
        *after* following symbolic links.
    """
    from betse.util.path import dirs, paths
    return any((paths.is_path(pathname) and (not dirs.is_dir(pathname)) for pathname in pathnames))

@type_check
def die_unless_file(*pathnames: str) -> None:
    """
    Raise an exception unless all passed paths are existing non-directory files
    *after* following symbolic links.

    Raises
    ----------
    BetseFileException
        If any passed path is *NOT* such a file.

    See Also
    ----------
    :func:`is_file`
        Further details.
    """
    if not is_file(*pathnames):
        for pathname in pathnames:
            if not is_file(*pathnames):
                raise BetseFileException('File "{}" not found or unreadable.'.format(pathname))

@type_check
def is_dir(dirname: str) -> bool:
    """
    ``True`` only if the directory with the passed dirname exists.

    Parameters
    -----------
    dirname : str
        Absolute or relative dirname of the directory to be tested.

    Returns
    -----------
    bool
        ``True`` only if this directory exists.
    """
    return os_path.isdir(dirname)

@type_check
def is_path(pathname: str) -> bool:
    """
    ``True`` only if the passed path exists *without* following this path if
    this path is an existing symbolic link.

    If this path is an existing **dangling symbolic link** (i.e., symbolic link
    whose target no longer exists, also commonly referred to as a broken
    symbolic link), this function still returns ``True``.
    """
    return os_path.lexists(pathname)

@type_check
def to_signed(array: NumpyArrayType) -> NumpyArrayType:
    """
    Convert the passed possibly unsigned Numpy array into a signed Numpy array
    exactly containing the same elements.

    If this array's data type is:

    * Already signed (e.g., :attr:`np.int32`, :attr:`np.float64`), this array is
      returned unmodified.
    * Unsigned (e.g., :attr:`np.uint8`), a new signed array preserving the
      contents of this array is returned.

    In the latter case, this array's contents are preserved across this data
    type conversion by doubling the precision of this array. Since signed and
    unsigned data types of the same bit width cover different integer ranges,
    creating a signed array of same bit width does *not* suffice to preserve
    this array's contents in the general case.

    For example, consider the following data types:

    * :attr:`np.uint16`, covering the integer range ``[0, 65535]``.
    * :attr:`np.int16`, covering the integer range ``[−32768, 32767]``.
    * :attr:`np.int32`, covering the integer range
      ``[−2147483648, 2147483647]``.

    If the data type of the passed array is :attr:`np.uint16`, this implies
    that only a data type of :attr:`np.int32` or wider (e.g., :attr:`np.int64`)
    suffices to preserve the contents of this array. Coercing these contents
    into an array of data type :attr:`np.int16` would destroy (e.g, truncate,
    wrap) *all* array elements in the integer range ``[32768, 65535]``.

    Parameters
    ----------
    array: NumpyArrayType
        Possibly unsigned Numpy array to be converted into a signed array.

    Returns
    -------
    NumpyArrayType
        Signed Numpy array converted from this possibly unsigned array.
    """
    dtype_signed = DTYPE_UNSIGNED_TO_SIGNED.get(array.dtype, None)
    return array if dtype_signed is None else dtype_signed(array)

@type_check
def load_image(filename: str, is_signed: bool=True, mode: ImageModeOrNoneTypes=None) -> NumpyArrayType:
    """
    Load the raw pixel data from the image with the passed filename into a
    multi-dimensional Numpy array and return this array.

    This array is guaranteed to be at least three-dimensional. Specifically, if
    this image is:

    * Greyscale, this array is three-dimensional such that:
      * The first dimension indexes each row of this image.
      * The second dimension indexes each column of the current row.
      * The third dimension indexes the grayscale value of the current pixel.
    * RGB or RGBA, this array is four-dimensional such that:
      * The first dimension indexes each row of this image.
      * The second dimension indexes each column of the current row.
      * The third dimension is either a 3-tuple ``(R, G, B)`` or 4-tuple
        ``(R, G, B, A)`` indexing each color component of the current pixel.
      * The fourth dimension indexes the value of the current color component.

    Caveats
    ----------
    When attempting to load user-defined images of arbitrary filetype, callers
    should pass the following parameters:

    * ``mode``.
    * ``is_signed`` to ``True``. Since this is (and *always* will be) the
      default, *not* passing this parameter satisfies this suggestion.

    Failure to do so invites subtle issues in computations falsely assuming the
    data type and shape of a returned array to be sane, which is *not* the case
    in common edge cases. Thanks to the heterogeneity of image file formats,
    returned arrays may exhibit anomalous features if any of these paremeters
    are *not* passed as suggested. In particular, the ``is_signed`` parameter
    should typically either *not* be passed or be passed as ``True``.

    Failure to do so instructs Pillow to produce an array with data type
    automatically corresponds to that of the input image. Since most (but *not*
    necessarily all) images reside in the :attr:`ImageModeType.COLOR_RGB` and
    :attr:`ImageModeType.COLOR_RGBA` colour spaces whose three- and
    four-channel pixel data is homogenously constrained onto unsigned bytes,
    most arrays returned by this function when explicitly passed an
    ``is_signed`` parameter of ``False`` will be **unsigned byte arrays**
    (i.e., arrays whose data types are :attr:`np.uint8`).

    Is that a subtle problem? **It is.**

    Python silently coerces scalar types as needed to preserve precision across
    operations that change precision. The canonical example is integer
    division.  In Python, dividing two integers that are *not* simple integer
    multiples of one another implicitly expands precision by producing a real
    number rather than integer (e.g., ``1 / 2 == 0.5`` rather than
    ``1 / 2 == 0``).

    On the other hand:

    * For all **signed Numpy arrays** (i.e., arrays whose data types are
      implicitly signed rather than explicitly unsigned), Numpy silently
      coerces the data types of these arrays as needed to preserve precision
      across precision-modifying operations.
    * For all **unsigned Numpy arrays** (i.e., arrays whose data types are
      explicitly unsigned rather than implicitly signed), Numpy silently
      preserves the unsigned facet of these arrays as needed by wrapping all
      numerical results to the integer range of these unsigned data types, thus
      discarding precision across precision-modifying operations.

    The canonical example is integer addition and substraction applied to
    unsigned byte arrays. Since unsigned bytes are confined to the integer
    range ``[0, 255]``, attempting to perform even seemingly trivial
    computation with unsigned byte arrays silently wraps results exceeding this
    range onto this range. The resulting arrays typically contain so-called
    "garbage data." As the following example shows, applying integer
    subtraction to signed but *not* unsigned Numpy arrays produces expected
    results:

        >>> import numpy as np
        >>> unsigned_garbage = np.array(((1,2), (3,4)), dtype=np.uint8)
        >>> unsigned_garbage[:,0] - unsigned_garbage[:,1]
        ... array([255, 255], dtype=uint8)
        >>> signed_nongarbage = np.array(((1,2), (3,4)))
        >>> signed_nongarbage[:,0] - signed_nongarbage[:,1]
        ... array([-1, -1])

    Design
    ----------
    This utility function is a thin wrapper around a similar function provided
    by some unspecified third-party dependency. This function currently wraps
    the :meth:`PIL.Image.open` method but previously wrapped the:

    * :func:`imageio.imread` function, which failed to expose support for
      colourspace conversion provided by Pillow.
    * :func:`scipy.misc.imread` function, which SciPy 1.0.0 formally deprecated
      and SciPy 1.2.0 permanently killed. Thus, SciPy 1.2.0 broke backward
      compatibility with downstream applications (notably, *this* application)
      requiring that API.

    This utility function principally exists to mitigate the costs associated
    with similar upstream API changes in the future. (We are ready this time.)

    Parameters
    ----------
    filename : str
        Absolute or relative filename of this image.
    is_signed : optional[bool]
        ``True`` only if converting the possibly unsigned array loaded from
        this image into a signed array. Defaults to ``True`` for the reasons
        detailed above. Since explicitly setting this to ``False`` invites
        errors in computations employing the returned array, callers should do
        so *ONLY* where these issues are acknowledged and handled
        appropriately.
    mode : ImageModeOrNoneTypes
        Type and depth of all pixels in the array loaded from this image,
        converted from this image's pixel data according to industry-standard
        image processing transforms implemented by :mod:`PIL`. Note that this
        is *not* the type and depth of all pixels in the input image, which
        :mod:`PIL` implicitly detects and hence requires no explicit
        designation. Defaults to ``None``, in which case no such conversion is
        performed (i.e., this image's pixel data is returned as is).

    Returns
    ----------
    ndarray
        Numpy array loaded from this image.
    """
    logs.log_debug('Loading image "%s"...', pathnames.get_basename(filename))
    files.die_unless_file(filename)
    image = Image.open(filename)
    if mode is not None and mode != image.mode:
        image = image.convert(mode.value)
    image_array = array(image)
    if is_signed:
        image_array = nparray.to_signed(image_array)
    return image_array

def interp2d_linear(x: NDArrayNdim1, y: NDArrayNdim1, z: NDArrayNdim2) -> Callable[[ndarray, ndarray], ndarray]:
    """
    Create and return a new **two-dimensional interpolator** (i.e., low-level
    callable interpolating a source mesh defined on the passed set of X and Y
    coordinates comprising a so-called "regular grid" and Z values (e.g.,
    colours) onto a target mesh defined on a new set of X and Y coordinates
    passed to that callable, which then returns the new Z values produced by
    that interpolation).

    This interpolator implements the "regular grid" code path of the obsolete
    :class:`scipy.interpolate.interp2d` class (passed the parameters
    ``kind='linear'`` and ``fill_value=0.0``) in terms of non-obsolete
    functionality defined by the :mod:`scipy.interpolate` subpackage, improving
    backward compatibility with existing code expecting that class to exist.

    Caveats
    -------
    This interpolator requires that the passed arrays satisfy these constraints:

    .. code-block:: python

       # The X and Y coordinates are *ALL* 1-dimensional: i.e.,
       x.ndim == y.ndim == 1

       # The Z values are 2-dimensional: i.e.,
       z.ndim == 2

       # The total number of X and Y coordinates differ: i.e.,
       x.size != y.size

       # The total number of Z values is the product of:
       # * The total number of X coordinates and...
       # * The total number of Y coordinates.
       z.size == x.size * y.size

    If any one of these constraints is *not* the case, an exception is raised.

    Parameters
    ----------
    x: NDArrayNdim1
        Source 1-dimensional X coordinates to interpolate from.
    y: NDArrayNdim1
        Source 1-dimensional Y coordinates to interpolate from.
    z: NDArrayNdim2
        Source 2-dimensional Z values to interpolate from.

    Returns
    -------
    Callable[[ndarray, ndarray], ndarray]
        Two-dimensional interpolator as described above. The signature of this
        callable should be assumed to be:

        .. code-block:: python

           def interpolator(x_new: ndarray, y_new: ndarray) -> ndarray: ...

    Raises
    ------
    BetseMathInterpolationException
        If any of the above constraints are violated.
    """
    if z.size != x.size * y.size:
        raise BetseMathInterpolationException(f'Interpolation Z shape not product of X and Y coordinates shape (i.e., "z.size = {z.size}" != "x.size = {x.size}" * "y.size = {y.size}").')
    bivariate_spline = RectBivariateSpline(x, y, z.T, kx=1, ky=1)
    bivariate_spline_interpolator = lambda x_new, y_new: bivariate_spline(x_new, y_new).T
    return bivariate_spline_interpolator

class ImageModeType(Enum):
    """
    Enumeration of all types of **image modes** (i.e., :mod:`PIL`-specific
    identifier defining both the type and depth of all pixels in an image)
    supported by functions defined by this submodule.

    This enumeration wraps the non-typesafe, non-human-readable ``mode`` string
    parameter commonly accepted by :mod:`PIL` functions (e.g.,
    :func:`PIL.Image.new`) with typesafe, human-readable variants. The value of
    each member of this enumeration is the corresponding ``mode`` string.

    Attributes
    ----------
    COLOR_RGB : enum
        Integer-based true color mode *without* alpha transparency, providing
        8-bit red, green, and blue pixels.
    COLOR_RGBA : enum
        Integer-based true color mode *with* alpha transparency, providing
        8-bit red, green, blue, and alpha transparency pixels.
    GRAYSCALE_INT : enum
        Integer-based grayscale mode, providing 8-bit black and white pixels.
        Converting color images *not* already in this mode to this mode reduces
        the resulting images to grayscale according to the ITU-R 601-2 luma
        transform in a lossy integer manner (i.e., ``L = R * 299/1000 + G *
        587/1000 + B * 114/1000`` for each pixel such that the fractional
        portion of each such ``L`` is discarded).
    GRAYSCALE_FLOAT : enum
        Floating point-based grayscale mode, providing 32-bit floating point
        pixels. Converting color images *not* already in this mode to this mode
        reduces the resulting images to grayscale according to the ITU-R 601-2
        luma transform in a lossy floating point manner (i.e., ``L = R *
        299/1000 + G * 587/1000 + B * 114/1000`` for each pixel such that the
        fractional portion of each such ``L`` is preserved). This conversion
        generalizes the integer-based conversion to grayscale performed by
        converting to the :attr:`GRAYSCALE_INT` mode by preserving rather than
        discarding the fractional portion of each luma value. Note that the
        only file format currently supporting images of this mode is TIFF.

    See Also
    ----------
    http://pillow.readthedocs.io/en/3.4.x/handbook/concepts.html#modes
        Most recent official documentation for Pillow modes.
    """
    COLOR_RGB = 'RGB'
    COLOR_RGBA = 'RGBA'
    GRAYSCALE_INT = 'I'
    GRAYSCALE_FLOAT = 'F'

class TissuePickerABC(object, metaclass=ABCMeta):
    """
    Abstract base class of all **tissue profile picker** (i.e., object
    assigning a subset of all cells matching some criteria to the corresponding
    tissue profile) subclasses.

    Typical criteria for matching cells includes explicit cell indexing,
    randomized cell selection, and image-defined spatial cell location.
    """

    @abstractmethod
    def pick_cells(self, cells: 'betse.science.cells.Cells', p: 'betse.science.parameters.Parameters') -> SequenceTypes:
        """
        One-dimensional Numpy array of the indices of all cells in the passed
        cell cluster selected by this tissue picker, ignoring extracellular
        spaces.

        Parameters
        ----------
        cells : Cells
            Current cell cluster.
        p : Parameters
            Current simulation configuration.

        Returns
        ----------
        SequenceTypes
            One-dimensional Numpy array of the indices of all such cells.
        """
        pass

    @type_check
    def pick_cells_and_mems(self, cells: 'betse.science.cells.Cells', p: 'betse.science.parameters.Parameters') -> tuple:
        """
        2-tuple ``(cells_index, mems_index)`` of one-dimensional Numpy arrays
        of the indices of both all cells *and* cell membranes in the passed
        cell cluster selected by this tissue picker, ignoring extracellular
        spaces.

        By default, this method returns the array returned by the subclass
        implementation of the abstract :meth:`pick_cells` method, mapped from
        cell to cell membrane indices.

        Parameters
        ----------
        cells : Cells
            Current cell cluster.
        p : Parameters
            Current simulation configuration.

        Returns
        ----------
        (ndarray, ndarray)
            2-tuple ``(cells_index, mems_index)``, where:
            * ``cells_index`` is the one-dimensional Numpy array of the indices
              of all subclass-selected cells.
            * ``mems_index`` is the one-dimensional Numpy array of the indices
              of all subclass-selected cell membranes.
        """
        cells_index = self.pick_cells(cells, p)
        mems_index = cells.cell_to_mems[cells_index]
        mems_index, _, _ = toolbox.flatten(mems_index)
        mems_index = nparray.from_iterable(mems_index)
        return (cells_index, mems_index)

class TissuePickerImageMask(object):
    """
    Cell profile-specific **image mask** (i.e., low-level object converting an
    well-formatted image into multiple SciPy-based interpolation functions
    clipping passed points to that image's colored pixel area).

    Design
    ----------
    This utility class is principally intended to be instantiated by the
    :class:`TissuePickerImage` class, but can (in theory) be instantiated
    directly by sufficiently careful external callers.

    This utility class is typically large in terms of memory consumption. Hence,
    the :class:`TissuePickerImage` class only locally instantiates instances of
    this class for the duration of method calls rather than permanently
    persisting such instances as instance variables of that class.

    Attributes
    ----------
    clipping_matrix : ndarray
        Numpy matrix defining this threshholded image.
    clipping_function : func
        SciPy-based interpolation function accepting an ``(x, y)`` point and
        returning ``1.0`` if that point resides outside this bitmap's colored
        pixel area or ``0.0`` otherwise. This function permits callers to filter
        a passed set of points in the space defined by :attr:`p.wsx` for the
        subset residing within this area.
    clipping_function_fast : func
        Fast variant of :attr:`clipping_function`, but otherwise sharing the
        same API.
    msize : int
        Size in pixels of each square dimension of this image, equivalent to
        both the width and height of this image.
    """

    @type_check
    def __init__(self, filename: str, x_min: NumericSimpleTypes, x_max: NumericSimpleTypes, y_min: NumericSimpleTypes, y_max: NumericSimpleTypes) -> None:
        """
        Load, initialize, and create a threshholded interpolation matrix from
        the passed image mask file.

        Format
        ----------
        This image should ideally be completely threshholded. Each pure black
        pixel (i.e., with red, green, and blue color components all 0) of this
        image collectively defines either:

        * The area to be used as the clipping mask for the cell cluster.
        * The area for a tissue, cut, or boundary profile.

        This image *must* additionally:

        * Be square (i.e., have equal pixel dimensions). For consistency, image
          dimensions of 500x500 pixels are recommended.
        * Contain *no* alpha transparency layer, a SciPy-based constraint and
          hence *not* amenable to change.

        Parameters
        ----------
        filename : str
            Absolute or relative filename of this image.
        x_min : NumericSimpleTypes
            Minimum X coordinate accepted by these interpolation functions.
        x_max : NumericSimpleTypes
            Maximum X coordinate accepted by these interpolation functions.
        y_min : NumericSimpleTypes
            Minimum Y coordinate accepted by these interpolation functions.
        y_max : NumericSimpleTypes
            Maximum Y coordinate accepted by these interpolation functions.

        Raises
        ----------
        BetseFileException
            If this image does *not* exist.
        BetseImageeException
            If this image has either:
            * Non-square dimensions (i.e., differing width and height).
            * An alpha transparency layer.
        """
        bitmap = pilnumpy.load_image(filename=filename, mode=ImageModeType.GRAYSCALE_FLOAT)
        if bitmap.shape[0] != bitmap.shape[1]:
            raise BetseImageException('Image "{}" dimensions non-square (i.e., width {} != height {}).'.format(filename, bitmap.shape[0], bitmap.shape[1]))
        point_inds = (bitmap != 255).nonzero()
        self.msize = bitmap.shape[0]
        self.clipping_matrix = np.zeros((self.msize, self.msize))
        self.clipping_matrix[point_inds] = 1.0
        self.clipping_matrix = np.flipud(self.clipping_matrix)
        xpts = np.linspace(x_min, x_max, self.msize)
        ypts = np.linspace(y_min, y_max, self.msize)
        xpts_2d_grid, ypts_2d_grid = np.meshgrid(xpts, ypts)
        xpts_2d = xpts_2d_grid.ravel()
        ypts_2d = ypts_2d_grid.ravel()
        clipping_matrix_2d = self.clipping_matrix.ravel()
        self.clipping_function = interp2d_linear(xpts, ypts, self.clipping_matrix)
        self.clipping_function_fast = RectBivariateSpline(xpts, ypts, self.clipping_matrix)
        Xclip, Yclip = np.meshgrid(xpts, ypts)
        indsN = (self.clipping_matrix == 1.0).nonzero()
        ptsx = Xclip[indsN].ravel()
        ptsy = Yclip[indsN].ravel()
        ppts = np.column_stack((ptsx, ptsy))
        bclip = ConvexHull(ppts)
        bverts = bclip.vertices
        bx = ptsx[bverts]
        by = ptsy[bverts]
        self.clipcurve = np.column_stack((bx, by))

    @type_check
    def get_clipped_points_index(self, points_x: SequenceTypes, points_y: SequenceTypes) -> ndarray:
        """
        One-dimensional Numpy array of the indices of all passed points that
        reside inside and are thus clipped by this image mask's colored area.

        Parameters
        -----------
        points_x : SequenceTypes
            Sequence of the X coordinates of all points to be clipped.
        points_y : SequenceTypes
            Sequence of the Y coordinates of all points to be clipped.

        Returns
        -----------
        ndarray
            One-dimensional Numpy array of the indices of all clipped points.
        """
        clipped_points_index = []
        for points_index, (x, y) in enumerate(zip(points_x, points_y)):
            if self.clipping_function(x, y) != 0.0:
                clipped_points_index.append(points_index)
        return np.asarray(clipped_points_index, dtype=int)

class TissuePickerImage(TissuePickerABC):
    """
    Image-based tissue picker, matching all cells residing inside the colored
    pixel area defined by an associated on-disk image mask file.

    Attributes
    ----------
    filename : str
        Absolute path of this image mask.
    """

    @type_check
    def __init__(self, filename: str, dirname: str) -> None:
        """
        Initialize this tissue picker.

        Parameters
        ----------
        filename : str
            Absolute or relative filename of this image mask. If relative (i.e.,
            *not* prefixed by a directory separator), this filename will be
            canonicalized into an absolute filename relative to the passed
            absolute dirname.
        dirname : str
            Absolute dirname of the directory containing this image mask. If the
            ``filename`` parameter is relative, that filename will be prefixed
            by this path to convert that filename into an absolute path; else,
            this dirname is ignored.
        """
        if pathnames.is_relative(filename):
            filename = pathnames.join(dirname, filename)
        files.die_unless_file(filename)
        self.filename = filename

    @type_check
    def pick_cells(self, cells: 'betse.science.cells.Cells', p: 'betse.science.parameters.Parameters') -> SequenceTypes:
        image_mask = self.get_image_mask(cells)
        clipped_points_index = image_mask.get_clipped_points_index(points_x=cells.cell_centres[:, 0], points_y=cells.cell_centres[:, 1])
        return clipped_points_index

    @type_check
    def get_image_mask(self, cells: 'betse.science.cells.Cells') -> TissuePickerImageMask:
        """
        Cell profile-specific image mask, abstracting the low-level pixels of
        this image file into higher-level Python objects.

        Parameters
        ----------
        cells : Cells
            Current cell cluster.

        Returns
        ----------
        TissuePickerImageMask
            Cell profile-specific image mask implementing this picker.
        """
        return TissuePickerImageMask(filename=self.filename, x_min=cells.xmin, x_max=cells.xmax, y_min=cells.ymin, y_max=cells.ymax)

class CallerTail:

    def make_voronoi_mesh_aliases(self, image_mask):
        self.ecm_verts = self.mesh.vcell_verts
        self.cluster_mask = image_mask.clipping_matrix
        self.msize = image_mask.msize
        self.ecm_verts_unique = self.mesh.vor_verts

    def cell_index(self, p) -> None:
        """
        (Re)define the array of all cell centres (i.e., :attr:`cell_centres`)
        from every corresponding Voronoi polygon.

        This method is typically called *after* creating, closing, and clipping
        the Voronoi diagram for this cell cluster. Doing so creates an ordering
        of cells consistent with all Voronoi polygons, membrane domains, and
        extracellular matrix (ECM)-driven polygons and segments.
        """
        self.cell_centres = self.mesh.vor_cents
        self.cell_vol = self.mesh.vor_sa * p.cell_height
