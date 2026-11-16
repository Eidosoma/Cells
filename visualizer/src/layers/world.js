// Where the things a run names stand on the picture. A run's view gives a tile to each
// cell and, for a small world, to each space outside the cells (an outside node). Two
// tiles that share an edge have a border. An entity of the run that joins two places (a
// junction, a face, a membrane, an exchange route, a channel population) is drawn on the
// border between their tiles, where both have one; otherwise it has no border, only the
// cell it lies on.
//
// Nothing here draws. The marks that show what crosses a border (./marks/stream.js) or
// what is dissipated at one (./marks/glow.js) ask it where to draw.

/** A tile's key in the maps below. */
const keyOf = (set, index) => `${set}:${index}`;

/**
 * The borders between tiles: every edge that exactly two tiles share. A tile is
 * { set, index, face, ring, centre }: the set it belongs to and its number there, its
 * corners as numbers in the shared list, the same corners as points, and its middle.
 * A border is { a, b, points, mid, along, across, length }: the two tiles, the edge's two
 * ends, its middle, the unit way along it, the unit way from a's middle to b's, its length.
 */
export function bordersOf(tiles) {
  const edges = new Map();
  for (const tile of tiles) {
    tile.face.forEach((vertex, k) => {
      const next = tile.face[(k + 1) % tile.face.length];
      const key = vertex < next ? `${vertex}:${next}` : `${next}:${vertex}`;
      if (!edges.has(key)) edges.set(key, []);
      edges.get(key).push({ tile, k });
    });
  }
  const borders = [];
  for (const sides of edges.values()) {
    if (sides.length !== 2) continue;
    const [{ tile: a, k }, { tile: b }] = sides;
    const from = a.ring[k], to = a.ring[(k + 1) % a.ring.length];
    const length = Math.hypot(to[0] - from[0], to[1] - from[1]) || 1;
    let ax = b.centre[0] - a.centre[0], ay = b.centre[1] - a.centre[1];
    const apart = Math.hypot(ax, ay) || 1;
    ax /= apart;
    ay /= apart;
    borders.push({ a, b, points: [from, to], mid: [(from[0] + to[0]) / 2, (from[1] + to[1]) / 2], along: [(to[0] - from[0]) / length, (to[1] - from[1]) / length], across: [ax, ay], length });
  }
  return borders;
}

/**
 * The places of one run on one picture. `tiles` are the picture's tiles (see bordersOf).
 * Gives back { tiles, borders, borderBetween(setA, a, setB, b), placeOf(setId, index) }.
 *
 * placeOf says where an entity of one of the run's sets is drawn:
 *   { border, first, cell }
 * `border` is the border it crosses, or null where its two places do not both have a tile;
 * `first` is the side of that border ("a" or "b") where the entity's first end lies: a
 * link's first entity (a junction's or a face's sender), or the cell of a membrane; `cell`
 * is the number of the cell it lies on, for a membrane and what lies on one, or null.
 * Null where the run's view does not say what the entity joins.
 */
export function worldOf(run, tiles) {
  const borders = bordersOf(tiles);
  const between = new Map();
  for (const border of borders) {
    between.set(`${keyOf(border.a.set, border.a.index)}|${keyOf(border.b.set, border.b.index)}`, { border, first: "a" });
    between.set(`${keyOf(border.b.set, border.b.index)}|${keyOf(border.a.set, border.a.index)}`, { border, first: "b" });
  }
  const borderBetween = (setA, a, setB, b) => between.get(`${keyOf(setA, a)}|${keyOf(setB, b)}`) || null;
  const placeOf = (setId, index) => {
    const set = run.sets.get(setId);
    const geometry = set?.geometry;
    if (!geometry) return null;
    if (geometry.kind === "links") {
      const ends = geometry.ends[index];
      if (!ends) return null;
      const found = borderBetween(geometry.between, ends[0], geometry.between, ends[1]);
      return { border: found?.border || null, first: found?.first || null, cell: null };
    }
    if (geometry.kind !== "on") return null;
    const on = geometry.index[index];
    if (on === undefined) return null;
    // What lies on a membrane (a channel population, an exchange route) stands where its membrane does.
    if (geometry.set !== "cell") return placeOf(geometry.set, on);
    const faces = set.outside;
    const found = faces ? borderBetween("cell", on, faces.set, faces.index[index]) : null;
    return { border: found?.border || null, first: found?.first || null, cell: on };
  };
  return { tiles, borders, borderBetween, placeOf };
}

/** The name of an entity's two ends, for a legend or a panel: "ecs_0 to bath", or "cell_0 and the space it faces". */
export function endsOf(run, setId, index) {
  const set = run.sets.get(setId);
  const geometry = set?.geometry;
  if (!geometry) return null;
  if (geometry.kind === "links") {
    const ends = geometry.ends[index], ids = run.sets.get(geometry.between)?.ids;
    return ends && ids ? { first: ids[ends[0]], second: ids[ends[1]] } : null;
  }
  if (geometry.kind !== "on") return null;
  const on = geometry.index[index];
  if (geometry.set !== "cell") return endsOf(run, geometry.set, on);
  const faces = set.outside;
  return { first: run.sets.get("cell")?.ids[on] ?? null, second: faces ? run.sets.get(faces.set)?.ids[faces.index[index]] ?? null : null };
}
