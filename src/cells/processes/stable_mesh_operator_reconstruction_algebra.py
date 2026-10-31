"""Bounded caller-owned rational matrices; no scientific imports or thresholds."""

from dataclasses import dataclass
from fractions import Fraction


@dataclass(frozen=True)
class Matrix:
    rows: int
    cols: int
    data: tuple

    def __post_init__(self):
        if (
            type(self.rows) is not int
            or type(self.cols) is not int
            or self.rows < 0
            or self.cols < 0
            or type(self.data) is not tuple
            or any(type(row) is not tuple for row in self.data)
            or len(self.data) != self.rows
            or any(len(row) != self.cols for row in self.data)
            or any(type(value) not in (int, Fraction) for row in self.data for value in row)
        ):
            raise ValueError("Require complete exact rational matrix dimensions/entries")


def matrix(rows, *, cols=None):
    original = tuple(tuple(row) for row in rows)
    if any(type(value) not in (int, Fraction) for row in original for value in row):
        raise ValueError("No implicit floating matrix conversion")
    rows = tuple(tuple(Fraction(value) for value in row) for row in original)
    ncols = len(rows[0]) if rows else cols
    if ncols is None:
        raise ValueError("Declare the column axis for an empty matrix")
    return Matrix(len(rows), ncols, rows)


def zeros(rows, cols):
    return Matrix(rows, cols, tuple(tuple(Fraction(0) for _ in range(cols)) for _ in range(rows)))


def identity(size):
    return matrix([[int(i == j) for j in range(size)] for i in range(size)], cols=size)


def transpose(value):
    return matrix(
        [[value.data[i][j] for i in range(value.rows)] for j in range(value.cols)], cols=value.rows
    )


def multiply(left, right):
    if left.cols != right.rows:
        raise ValueError("Exact matrix owner axes differ")
    return matrix(
        [
            [
                sum((left.data[i][k] * right.data[k][j] for k in range(left.cols)), Fraction(0))
                for j in range(right.cols)
            ]
            for i in range(left.rows)
        ],
        cols=right.cols,
    )


def subtract(left, right):
    if (left.rows, left.cols) != (right.rows, right.cols):
        raise ValueError("Exact residual matrix owner axes differ")
    return matrix(
        [[left.data[i][j] - right.data[i][j] for j in range(left.cols)] for i in range(left.rows)],
        cols=left.cols,
    )


def scale_rows(value, weights):
    if len(weights) != value.rows:
        raise ValueError("Row metric axis differs")
    return matrix(
        [[weights[i] * entry for entry in row] for i, row in enumerate(value.data)], cols=value.cols
    )


def scale_columns(value, weights):
    if len(weights) != value.cols:
        raise ValueError("Column metric axis differs")
    return matrix(
        [[entry * weights[j] for j, entry in enumerate(row)] for row in value.data], cols=value.cols
    )


def negative(value):
    return scale_rows(value, [-1] * value.rows)


def rref(value, *, pivot_cols=None, journal=None, label="rref"):
    limit = value.cols if pivot_cols is None else pivot_cols
    if not 0 <= limit <= value.cols:
        raise ValueError("Unsupported exact pivot column axis")
    rows, pivots = [list(row) for row in value.data], []
    for column in range(limit):
        row = len(pivots)
        chosen = next((i for i in range(row, value.rows) if rows[i][column]), None)
        if chosen is None:
            continue
        event = dict(
            label=label,
            step=row,
            column=column,
            chosen_row=chosen,
            before=matrix(rows, cols=value.cols),
        )
        if journal is not None:
            journal.append(event)
        try:
            rows[row], rows[chosen] = rows[chosen], rows[row]
            pivot = rows[row][column]
            rows[row] = [entry / pivot for entry in rows[row]]
            for i in range(value.rows):
                if i != row:
                    coefficient = rows[i][column]
                    rows[i] = [
                        entry - coefficient * p for entry, p in zip(rows[i], rows[row], strict=True)
                    ]
            event["after"] = matrix(rows, cols=value.cols)
            pivots.append(column)
        except Exception as error:
            event["failure"] = dict(
                type=type(error).__name__, reason=str(error), partial=matrix(rows, cols=value.cols)
            )
            raise
    return matrix(rows, cols=value.cols), tuple(pivots)


def inverse(value, *, journal=None, label="inverse"):
    if value.rows != value.cols or value.rows == 0:
        raise ValueError("Only an explicitly nonsingular square Gram matrix can be inverted")
    size = value.rows
    augmented = matrix(
        [list(row) + list(identity(size).data[i]) for i, row in enumerate(value.data)]
    )
    reduced, pivots = rref(augmented, pivot_cols=size, journal=journal, label=label)
    if pivots != tuple(range(size)):
        raise ValueError("Singular exact Gram matrix; no cutoff, ridge or inverse substitution")
    return matrix([row[size:] for row in reduced.data])


def pseudoinverse(value, *, journal=None):
    reduced, pivots = rref(value, journal=journal, label="D0_rref")
    rank = len(pivots)
    if rank == 0:
        return zeros(value.cols, value.rows), dict(
            rank=0,
            pivot_columns=pivots,
            column_factor=zeros(value.rows, 0),
            row_factor=zeros(0, value.cols),
        )
    column = matrix([[row[j] for j in pivots] for row in value.data])
    row = matrix(reduced.data[:rank], cols=value.cols)
    gc = multiply(transpose(column), column)
    gr = multiply(row, transpose(row))
    gc_inv = inverse(gc, journal=journal, label="gramC_inverse")
    gr_inv = inverse(gr, journal=journal, label="gramR_inverse")
    result = multiply(multiply(multiply(transpose(row), gr_inv), gc_inv), transpose(column))
    return result, dict(
        rank=rank,
        pivot_columns=pivots,
        column_factor=column,
        row_factor=row,
        column_gram=gc,
        row_gram=gr,
        column_gram_inverse=gc_inv,
        row_gram_inverse=gr_inv,
    )


def nullspace(value, *, journal=None, label="nullspace_rref"):
    reduced, pivots = rref(value, journal=journal, label=label)
    free = [column for column in range(value.cols) if column not in pivots]
    basis = [[Fraction(0)] * len(free) for _ in range(value.cols)]
    for j, column in enumerate(free):
        basis[column][j] = Fraction(1)
        for row, pivot in enumerate(pivots):
            basis[pivot][j] = -reduced.data[row][column]
    return matrix(basis, cols=len(free))
