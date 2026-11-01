# Copyright 2014-2025 Alexis Pietak & Cecil Curry; see licenses/BETSE.txt.
"""Literal selected environmental Poisson statements and original MAC Laplacian.

The phase/callback make_world driver and subsequent lapGJ stores are excluded.
"""
# ruff: noqa: B006,B007,E501

import numpy as np

CELLS_SHA256 = 'be38678a4f0bd084044fe7d952d74a4550003ce9701f5d073d1f124ba6daeaf2'
GRID_SHA256 = '8186bc5c013db8aec224f6ed9b0892e944b2ddd4247f135ff19caf7419478350'
CALLER_LINES = ((503, 504), (511, 512))
GRID_LINES = (252, 431)


# fmt: off
class CellsPoisson:
    def environment_voltage(self):
        bdic = {'N': 'value', 'S': 'value', 'E': 'value', 'W': 'value'}
        _, self.lapENVinv = self.grid_obj.makeLaplacian(bound=bdic)

    def environment_current(self):
        bdic = {'N': 'flux', 'S': 'flux', 'E': 'flux', 'W': 'flux'}
        _, self.lapENV_P_inv = self.grid_obj.makeLaplacian(bound=bdic)


class FiniteDiffPoisson:
    def makeLaplacian(self, bound = {'N':'value','S':'value','E':'value','W':'value'}):
        """
        Calculate a Laplacian operator matrix suitable for solving a 2D Poisson equation
        on a regular Cartesian grid with square boundaries. Note: the graph must have
        equal spacing in the x and y directions (the same delta in x and y directions).

        """

        size_rows = self.cents_shape[0]
        size_cols = self.cents_shape[1]

        sze = size_rows*size_cols

        A = np.zeros((sze,sze))

        for k, (i,j) in enumerate(self.map_ij2k_cents):

            # if we're not on a main boundary:
            if i != 0 and j != 0 and i != size_rows-1 and j != size_cols-1:

                k_ip1_j = self.map_ij2k_cents.tolist().index([i + 1,j])
                k_in1_j = self.map_ij2k_cents.tolist().index([i-1,j])
                k_i_jp1 = self.map_ij2k_cents.tolist().index([i,j+1])
                k_i_jn1 = self.map_ij2k_cents.tolist().index([i,j-1])

                A[k, k_ip1_j] = 1
                A[k, k_in1_j] = 1
                A[k, k_i_jp1] = 1
                A[k, k_i_jn1] = 1
                A[k,k] = -4


            elif i == 0 and j != 0 and j != size_cols -1: # if on the bottom (South) boundary:

                if bound['S'] == 'flux':

                    k_ip1_j = self.map_ij2k_cents.tolist().index([i + 1,j])
                    k_i_jp1 = self.map_ij2k_cents.tolist().index([i,j+1])
                    k_i_jn1 = self.map_ij2k_cents.tolist().index([i,j-1])

                    A[k, k_ip1_j] = 1
                    A[k, k_i_jp1] = 1
                    A[k, k_i_jn1] = 1

                    A[k,k] = -3

                elif bound['S'] == 'value':

                    k_ip1_j = self.map_ij2k_cents.tolist().index([i + 1,j])

                    A[k,k] = 1
                    # A[k,k_ip1_j] = 1

            elif i == size_rows -1 and j != 0 and j != size_cols -1: # if on the top (North) boundary:

                if bound['N'] == 'flux':

                    k_in1_j = self.map_ij2k_cents.tolist().index([i-1,j])
                    k_i_jp1 = self.map_ij2k_cents.tolist().index([i,j+1])
                    k_i_jn1 = self.map_ij2k_cents.tolist().index([i,j-1])

                    A[k, k_in1_j] = 1
                    A[k, k_i_jp1] = 1
                    A[k, k_i_jn1] = 1

                    A[k,k] = -3

                elif bound['N'] == 'value':

                    k_in1_j = self.map_ij2k_cents.tolist().index([i-1,j])

                    A[k,k] = 1
                    # A[k,k_in1_j] = 1

            elif j == 0 and i != 0 and i != size_rows -1:  # if on the left (West) boundary:

                if bound['W'] == 'flux':

                    k_i_jp1 = self.map_ij2k_cents.tolist().index([i,j+1])
                    k_ip1_j = self.map_ij2k_cents.tolist().index([i + 1,j])
                    k_in1_j = self.map_ij2k_cents.tolist().index([i-1,j])

                    A[k, k_i_jp1] = 1
                    A[k, k_ip1_j] = 1
                    A[k, k_in1_j] = 1

                    A[k,k] = -3

                elif bound['W'] == 'value':

                    k_i_jp1 = self.map_ij2k_cents.tolist().index([i,j+1])

                    A[k,k] = 1
                    # A[k,k_i_jp1] = 1

            elif j == size_cols -1 and i != 0 and i != size_rows -1: # if on the right (East) boundary:

                if bound['E'] == 'flux':

                    k_i_jn1 = self.map_ij2k_cents.tolist().index([i,j-1])
                    k_ip1_j = self.map_ij2k_cents.tolist().index([i + 1,j])
                    k_in1_j = self.map_ij2k_cents.tolist().index([i-1,j])

                    A[k, k_i_jn1] = 1
                    A[k, k_ip1_j] = 1
                    A[k, k_in1_j] = 1

                    A[k,k] = -3

                elif bound['E'] == 'value':

                    k_i_jn1 = self.map_ij2k_cents.tolist().index([i,j-1])

                    A[k,k] = 1
                    # A[k,k_i_jn1] = 1

            # corners:
            elif i == 0 and j == 0: # SW corner

                if bound['S'] == 'flux':

                    k_ip1_j = self.map_ij2k_cents.tolist().index([i + 1,j])
                    k_i_jp1 = self.map_ij2k_cents.tolist().index([i,j+1])

                    A[k, k_i_jp1] = 1
                    A[k, k_ip1_j] = 1
                    A[k,k] = -2

                else:
                    A[k,k] = 1

            elif i == size_rows - 1 and j == 0: # NW corner

                if bound['N'] == 'flux':

                    k_in1_j = self.map_ij2k_cents.tolist().index([i - 1,j])
                    k_i_jp1 = self.map_ij2k_cents.tolist().index([i,j+1])

                    A[k, k_i_jp1] = 1
                    A[k, k_in1_j] = 1
                    A[k,k] = -2

                else:
                    A[k,k] = 1

            elif i == 0 and j == size_cols - 1: # SE corner

                if bound['E'] == 'flux':

                    k_ip1_j = self.map_ij2k_cents.tolist().index([i + 1,j])
                    k_i_jn1 = self.map_ij2k_cents.tolist().index([i,j-1])

                    A[k, k_i_jn1] = 1
                    A[k, k_ip1_j] = 1
                    A[k,k] = -2

                else:
                    A[k,k] = 1

            elif i == size_rows - 1 and j == size_cols - 1: # NE corner

                if bound['E'] == 'flux':

                    k_in1_j = self.map_ij2k_cents.tolist().index([i - 1,j])
                    k_i_jn1 = self.map_ij2k_cents.tolist().index([i,j-1])

                    A[k, k_i_jn1] = 1
                    A[k, k_in1_j] = 1
                    A[k,k] = -2

                else:
                    A[k,k] = 1


        A = A/(self.delta**2)

        # calculate the inverse, which is stored for solution calculation of Laplace and Poisson equations
        Ainv = np.linalg.pinv(A)

        return A, Ainv

# fmt: on
