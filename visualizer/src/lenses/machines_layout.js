// Where the Machines view puts each tray and each machine: a pure function of the machines of
// the species shown, kept apart from the view so the tests can read it. One unit of the scene is
// ten nanometres, so every shape drawn to scale is drawn at its size in the same units; a card
// (a machine with no size in hand) has one size for all, and the legend says it is not to scale.

/** Ten nanometres to one unit of the scene. */
export const UNIT_NM = 10;
/** A card: a flat label lying on its tray. Not to scale. */
export const CARD = { w: 9.6, d: 3.4, h: 0.32, gap: 0.9 };
/** A tray: its rim's height, the room inside its edge, the space between two trays, the room for its name, and how many cards across. */
export const TRAY = { h: 0.9, pad: 2.6, gap: 4.2, head: 3.4, across: 3, wideAcross: 6, letter: 0.75 };
/** The bench the trays lie on, past the trays on each side. */
export const BENCH = { pad: 4, h: 1.2 };
/** The scale bar etched on the bench: this many nanometres. */
export const SCALE_NM = 100;
/** The space between two shapes standing in a tray. */
const BETWEEN = 3;
/** Where no box of a shape is known yet (a machine whose file is still being read), this much room. */
export const PENDING = { w: 8, d: 8, h: 10 };

/** A shape's box in the scene's units, from what the catalogue says of its size (null for a card). */
export function shapeOf(item, measured = null) {
  const size = item.entry?.size;
  if (size?.shape === "measured" && (size.parts?.length || size.whole?.axes)) {
    // Bodies measured by the viewer from a structure (tools/measure_particle.py): each an ellipsoid at its centre and
    // along its own axes, in the machine's frame (y up). The box round every body it may draw gives the room it takes.
    const lo = [Infinity, Infinity, Infinity], hi = [-Infinity, -Infinity, -Infinity];
    for (const body of [...bodiesAt(size, 1), ...bodiesAt(size, 2), ...bodiesAt(size, 3)]) {
      const half = body.across_nm.map((n) => n / UNIT_NM / 2);
      for (let i = 0; i < 3; i++) {
        const reach = Math.sqrt(body.axes.reduce((sum, axis, k) => sum + (axis[i] * half[k]) ** 2, 0));
        const middle = body.centre_nm[i] / UNIT_NM;
        lo[i] = Math.min(lo[i], middle - reach);
        hi[i] = Math.max(hi[i], middle + reach);
      }
    }
    return { kind: "measured", parts: size.parts || [], chains: size.chains || [], outline: size.outline, whole: size.whole, lo, hi, w: hi[0] - lo[0], h: hi[1] - lo[1], d: hi[2] - lo[2] };
  }
  if (size?.shape === "ellipsoid") {
    // Its three widths as its species' file states them, the longest along the tray and the shortest upright.
    const [w, d, h] = [...size.across_nm].sort((a, b) => b - a).map((n) => n / UNIT_NM);
    return { kind: "ellipsoid", w, d, h };
  }
  if (size?.shape === "rod") {
    const length = Math.max(...size.long_nm) / UNIT_NM;
    // Its width is the picture's choice (the panel says so): a quarter of its length.
    const radius = length / 8;
    return { kind: "rod", length, radius, w: length, d: 2 * radius, h: 2 * radius };
  }
  if (item.entry?.closer) {
    const box = measured || PENDING;
    return { kind: "machine", file: item.entry.closer.file, w: box.w, d: box.d, h: box.h, pending: !measured };
  }
  return null;
}

/**
 * The bodies a measured machine draws at a level: 1, its outline (its named parts, or the whole where the overlay says
 * the whole is its outline); 2, its named parts; 3, each chain. A level it has nothing for falls back to the one before.
 */
export function bodiesAt(size, level) {
  const whole = size.whole?.axes ? [{ id: null, across_nm: size.whole.across_nm, centre_nm: [0, 0, 0], axes: size.whole.axes }] : [];
  const outline = size.outline === "whole" && whole.length ? whole : size.parts?.length ? size.parts : whole;
  if (level >= 3 && size.chains?.length) return size.chains;
  if (level >= 2 && size.parts?.length) return size.parts;
  return outline;
}

/**
 * The layout for a species' machines (Catalogue.of): trays in rows, the membrane machines with
 * laws in one wide tray behind the others; in each tray its shapes first, standing in a row at
 * their own sizes, then its cards in a grid. `columns` is how many trays stand side by side.
 */
export function layoutOf(items, groups, { columns = 3, measured = {}, ions = "ions" } = {}) {
  const byGroup = new Map();
  for (const item of items) {
    if (!byGroup.has(item.group)) byGroup.set(item.group, []);
    byGroup.get(item.group).push(item);
  }
  const ordered = groups.filter((group) => byGroup.has(group.id));
  const small = ordered.filter((group) => group.id !== ions), wide = ordered.filter((group) => group.id === ions);
  const columnsUsed = Math.max(1, Math.min(columns, small.length || 1));
  // A tray is as wide as its widest row of shapes, its cards (three across) or its name, whichever is widest; the small
  // trays share one width, so that they stand in columns; the tray of the machines with laws is at least six cards wide.
  const cardsWide = (across) => across * (CARD.w + CARD.gap) - CARD.gap;
  const need = (group) => {
    const members = byGroup.get(group.id);
    const shapes = members.map((item) => shapeOf(item, measured[item.id])).filter(Boolean);
    const cards = members.length - shapes.length;
    const row = shapes.reduce((sum, shape) => sum + shape.w, 0) + Math.max(0, shapes.length - 1) * BETWEEN;
    return 2 * TRAY.pad + Math.max(Math.min(row, 60), cards ? cardsWide(Math.min(cards, TRAY.across)) : 0, group.label.length * TRAY.letter + 1.2);
  };
  const trayWidth = Math.max(16, ...small.map(need));
  const rowsWidth = columnsUsed * trayWidth + (columnsUsed - 1) * TRAY.gap;
  const fullWidth = Math.max(rowsWidth, wide.length ? 2 * TRAY.pad + cardsWide(columns > 1 ? TRAY.wideAcross : 3) : 0);
  const trays = [], placed = [];
  const fill = (group, width) => {
    const inside = width - 2 * TRAY.pad;
    const members = byGroup.get(group.id);
    const shapes = members.map((item) => ({ item, shape: shapeOf(item, measured[item.id]) })).filter((entry) => entry.shape);
    const cards = members.filter((item) => !shapeOf(item, measured[item.id]));
    const out = [];
    // The shapes, in a row from the left, each at its own size; a row that is full goes on below.
    let x = 0, z = TRAY.pad, rowDepth = 0;
    for (const { item, shape } of shapes) {
      if (x > 0 && x + shape.w > inside) { x = 0; z += rowDepth + BETWEEN; rowDepth = 0; }
      out.push({ id: item.id, item, type: "shape", shape, x: x + shape.w / 2, z: z + shape.d / 2, w: shape.w, d: shape.d, h: shape.h });
      x += shape.w + BETWEEN;
      rowDepth = Math.max(rowDepth, shape.d);
    }
    if (shapes.length) z += rowDepth + BETWEEN;
    // The cards, in a grid.
    const across = Math.max(1, Math.floor((inside + CARD.gap) / (CARD.w + CARD.gap)));
    cards.forEach((item, index) => {
      const column = index % across, row = Math.floor(index / across);
      out.push({ id: item.id, item, type: "card", x: column * (CARD.w + CARD.gap) + CARD.w / 2, z: z + row * (CARD.d + CARD.gap) + CARD.d / 2, w: CARD.w, d: CARD.d, h: CARD.h });
    });
    if (cards.length) z += Math.ceil(cards.length / across) * (CARD.d + CARD.gap) - CARD.gap;
    // Its name, in a strip along its front, where no shape standing in it can hide it.
    return { out, depth: z + 0.8 + TRAY.head };
  };
  // The small trays, in rows from the front; each row as deep as its deepest tray.
  let front = 0;
  const rows = [];
  for (let start = 0; start < small.length; start += columnsUsed) rows.push(small.slice(start, start + columnsUsed));
  const rowsFrontToBack = rows;
  for (const row of rowsFrontToBack) {
    const filled = row.map((group) => ({ group, ...fill(group, trayWidth) }));
    const depth = Math.max(...filled.map((tray) => tray.depth));
    filled.forEach((tray, index) => {
      const left = -rowsWidth / 2 + index * (trayWidth + TRAY.gap);
      const back = front - depth;
      trays.push({ group: tray.group.id, label: tray.group.label, x: left + trayWidth / 2, z: back + depth / 2, w: trayWidth, d: depth });
      for (const entry of tray.out) placed.push({ ...entry, group: tray.group.id, x: left + TRAY.pad + entry.x, z: back + entry.z, y: TRAY.h });
    });
    front -= depth + TRAY.gap;
  }
  // The membrane machines with laws: one tray as wide as the rows, behind them.
  for (const group of wide) {
    const tray = fill(group, fullWidth);
    const back = front - tray.depth;
    trays.push({ group: group.id, label: group.label, x: 0, z: back + tray.depth / 2, w: fullWidth, d: tray.depth });
    for (const entry of tray.out) placed.push({ ...entry, group: group.id, x: -fullWidth / 2 + TRAY.pad + entry.x, z: back + entry.z, y: TRAY.h });
    front -= tray.depth + TRAY.gap;
  }
  const minX = -fullWidth / 2 - BENCH.pad, maxX = fullWidth / 2 + BENCH.pad;
  const maxZ = BENCH.pad + 6, minZ = front + TRAY.gap - BENCH.pad;
  const maxY = Math.max(TRAY.h + 1, ...placed.map((entry) => entry.y + entry.h));
  const sized = placed.some((entry) => entry.type === "shape");
  return {
    trays,
    items: placed,
    bench: { x: 0, z: (minZ + maxZ) / 2, w: maxX - minX, d: maxZ - minZ },
    scale: sized ? { x: -rowsWidth / 2, z: 3.2, length: SCALE_NM / UNIT_NM, nm: SCALE_NM } : null,
    bounds: { minX, maxX, minZ, maxZ, maxY },
    columns: columnsUsed,
  };
}
