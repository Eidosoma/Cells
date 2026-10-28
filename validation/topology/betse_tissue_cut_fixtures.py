"""Small manufactured adjacent 4/5/6-sided cells and explicit stable identities."""


def geometry():
    s = 1e-5
    polygons = [
        [[0, 0], [1, 0], [1, 1], [0, 1]],
        [[1, 0], [2, 0], [2, 1], [1.5, 1.2], [1, 1]],
        [[2, 0], [3, 0], [3.2, 0.5], [3, 1], [2.5, 1.2], [2, 1]],
    ]
    return dict(
        cell_ids=["A", "B", "C"],
        centres_m=[[0.5 * s, 0.5 * s], [1.5 * s, 0.5 * s], [2.5 * s, 0.6 * s]],
        polygons_m=[[[s * x, s * y] for x, y in poly] for poly in polygons],
        scale_cell=0.9,
        cell_space=1e-6,
        cell_radius=5e-6,
        cell_height=1e-5,
        tm=7.5e-9,
        grid_min_m=-0.2 * s,
        grid_max_m=3.4 * s,
        grid_count=8,
    )


def cases():
    return [
        dict(name="cut-" + label, remove_cell_ids=[cell_id], geometry=geometry())
        for label, cell_id in (("left", "A"), ("middle", "B"), ("right", "C"))
    ]
