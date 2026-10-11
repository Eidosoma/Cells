"""The dodecahedron as the generalized Petersen graph G(10, 2).

Vertices 0..9 form an outer decagon, 10..19 two inner pentagons. Spokes
join i to i+10. Geometry is prescribed; occupied vertices induce contacts.
"""

NODES = 20
FULL = (1 << NODES) - 1
TOPOLOGY_ID = "dodecahedron_g10_2@1"
EDGES = tuple(
    sorted(
        {
            tuple(sorted(edge))
            for i in range(10)
            for edge in ((i, (i + 1) % 10), (i, i + 10), (i + 10, (i + 2) % 10 + 10))
        }
    )
)
NEIGHBORS = tuple(
    tuple(b if a == node else a for a, b in EDGES if node in (a, b)) for node in range(NODES)
)
NEIGHBOR_MASKS = tuple(sum(1 << n for n in row) for row in NEIGHBORS)
RING = (10, 12, 14, 16, 18)
OPEN_CHAIN = (10, 0, 1, 2, 3)


def mask_of(nodes):
    return sum(1 << node for node in nodes)


def component(mask, root, cut=None):
    """Independent host BFS; also used to validate complete checkpoints."""
    reached = {root} if mask & (1 << root) else set()
    todo = list(reached)
    while todo:
        node = todo.pop()
        for neighbor in NEIGHBORS[node]:
            if cut is not None and tuple(sorted((node, neighbor))) == cut:
                continue
            if mask & (1 << neighbor) and neighbor not in reached:
                reached.add(neighbor)
                todo.append(neighbor)
    return mask_of(reached)
