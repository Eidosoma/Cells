// Where the Machines view puts each tray and each machine: a pure function of the machines of
// the species shown, kept apart from the view so the tests can read it. One unit of the scene is
// ten nanometres, so every shape drawn to scale is drawn at its size in the same units; a card
// (a machine with no size in hand) has one size for all, and the legend says it is not to scale.

/** Ten nanometres to one unit of the scene. */
export const UNIT_NM = 10;
/** A card: a flat label lying on its tray. Not to scale. */
export const CARD = { w: 9.6, d: 3.4, h: 0.32, gap: 0.9 };
/**
 * A tray: its rim's height, the room inside its edge, the space between two trays, how many cards across, the height
 * of the letters of its name (one line, or two where it is long) and its least width. A tray is as wide as its shapes,
 * its cards or its name need, so that machines of ten to thirty nanometres do not stand in trays ten times as wide.
 */
export const TRAY = { h: 0.9, pad: 1.6, gap: 3, across: 3, wideAcross: 6, name: 1, least: 8 };
/** A tray's name in one line, or in two of about the same length where it is long. */
export function nameLines(label) {
  if (label.length <= 18) return [label];
  const words = label.split(" ");
  let best = [label], most = Infinity;
  for (let k = 1; k < words.length; k++) {
    const lines = [words.slice(0, k).join(" "), words.slice(k).join(" ")];
    const longest = Math.max(...lines.map((line) => line.length));
    if (longest < most) [best, most] = [lines, longest];
  }
  return best;
}
/** The room along a tray's front that its name takes: its lines, and a margin behind the front rim, which hides what lies close to it. */
export const headOf = (lines) => lines.length * TRAY.name * 1.25 + 1.6;
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
  const size = item.size;
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
    return { kind: "measured", parts: size.parts || [], chains: size.chains || [], outline: size.outline, whole: size.whole, membrane: size.membrane || null, lo, hi, w: hi[0] - lo[0], h: hi[1] - lo[1], d: hi[2] - lo[2] };
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

/** The named part that holds a chain: by the chain's entity, or by the chain itself where the part is named by chains. */
export function partOfChain(size, chain) {
  return size.parts?.find((part) => (chain.entity && part.entities?.includes(chain.entity)) || part.chains?.includes(chain.id)) || null;
}

/**
 * Whether a measured machine's parts are drawn as their chains: it has both, and every chain is in a named part. A part
 * as one ellipsoid of the same spread misleads where its chains lie apart (the ATP synthase's peripheral stalk, b2 and
 * δ, is a slab 29 nm long that hides the rest); its own ellipsoid stays its size, in its panel.
 */
export function partsByChains(size) {
  return Boolean(size.parts?.length && size.chains?.length) && size.chains.every((chain) => partOfChain(size, chain));
}

/**
 * The bodies a measured machine draws at a level: 1, its outline (its named parts, as their chains where it has them,
 * or the whole where the overlay says the whole is its outline); 2, its named parts, each as its chains where it has
 * them (a chain's body then carries its part's id); 3, each chain. A level it has nothing for falls back to the one before.
 */
export function bodiesAt(size, level) {
  const whole = size.whole?.axes ? [{ id: null, across_nm: size.whole.across_nm, centre_nm: [0, 0, 0], axes: size.whole.axes }] : [];
  if (level >= 3 && size.chains?.length) return size.chains;
  const byChains = partsByChains(size) ? size.chains.map((chain) => ({ ...chain, part: partOfChain(size, chain).id })) : null;
  if (level >= 2 && size.parts?.length) return byChains || size.parts;
  if (size.outline === "whole" && whole.length) return whole;
  return byChains || (size.parts?.length ? size.parts : whole);
}

/**
 * Where a measured machine's membrane lies, where the catalogue names its part in the membrane: centred on that part,
 * as thick as that part's farthest atoms reach along the machine's axis (y, the measure's frame), each of its own
 * axes' extent projected on it as an ellipsoid's is. Null where no part is named.
 */
export function membraneOf(size) {
  const part = size?.membrane && size.parts?.find((value) => value.id === size.membrane.part);
  if (!part) return null;
  const extent = part.farthest_nm || part.across_nm;
  const thick = Math.sqrt(part.axes.reduce((sum, axis, k) => sum + (axis[1] * extent[k]) ** 2, 0));
  return { part, centre_nm: part.centre_nm[1], thick_nm: Math.round(thick * 10) / 10 };
}

/**
 * The layout for a species' machines (Catalogue.of): trays in rows, the units of the law inventory
 * in one wide tray behind them, and behind that the trays of the groups the catalogue says stand
 * behind (a group's `stands: "behind"`, with its reason beside it: a tray whose shapes are so large
 * that, further forward, they would hide what stands behind them); in each tray its cards in a grid
 * at the back, then its shapes in front, standing in rows at their own sizes. `columns` is how many
 * trays stand side by side.
 */
export function layoutOf(items, groups, { columns = 3, measured = {}, ions = "ions" } = {}) {
  const byGroup = new Map();
  for (const item of items) {
    if (!byGroup.has(item.group)) byGroup.set(item.group, []);
    byGroup.get(item.group).push(item);
  }
  const ordered = groups.filter((group) => byGroup.has(group.id));
  const behind = ordered.filter((group) => group.id !== ions && group.stands === "behind");
  const small = ordered.filter((group) => group.id !== ions && group.stands !== "behind"), wide = ordered.filter((group) => group.id === ions);
  const columnsUsed = Math.max(1, Math.min(columns, small.length || 1));
  // A tray is as wide as its widest row of shapes, its cards (three across) or its name, whichever is widest, and no
  // narrower than the least; each row of trays is centred; the tray of the law inventory's units is at least six cards wide.
  const cardsWide = (across) => across * (CARD.w + CARD.gap) - CARD.gap;
  const need = (group) => {
    const members = byGroup.get(group.id);
    const shapes = members.map((item) => shapeOf(item, measured[item.id])).filter(Boolean);
    const cards = members.length - shapes.length;
    const row = shapes.reduce((sum, shape) => sum + shape.w, 0) + Math.max(0, shapes.length - 1) * BETWEEN;
    const name = Math.max(...nameLines(group.label).map((line) => line.length)) * 0.56 * TRAY.name + 1.2;
    return Math.max(TRAY.least, 2 * TRAY.pad + Math.max(Math.min(row, 60), cards ? cardsWide(Math.min(cards, TRAY.across)) : 0, name));
  };
  const rows = [], backRows = [];
  for (let start = 0; start < small.length; start += columnsUsed) rows.push(small.slice(start, start + columnsUsed));
  for (let start = 0; start < behind.length; start += columnsUsed) backRows.push(behind.slice(start, start + columnsUsed));
  const widthOf = (row) => row.reduce((sum, group) => sum + need(group), 0) + (row.length - 1) * TRAY.gap;
  const rowsWidth = Math.max(0, ...rows.map(widthOf));
  const fullWidth = Math.max(rowsWidth, ...backRows.map(widthOf), wide.length ? 2 * TRAY.pad + cardsWide(columns > 1 ? TRAY.wideAcross : 3) : 0);
  const trays = [], placed = [];
  const fill = (group, width) => {
    const inside = width - 2 * TRAY.pad;
    const members = byGroup.get(group.id);
    const shapes = members.map((item) => ({ item, shape: shapeOf(item, measured[item.id]) })).filter((entry) => entry.shape);
    const cards = members.filter((item) => !shapeOf(item, measured[item.id]));
    const out = [];
    let z = TRAY.pad;
    // The cards, in a grid at the back; the shapes in front of them, nearer the eye, where the cards cannot hide them.
    const across = Math.max(1, Math.floor((inside + CARD.gap) / (CARD.w + CARD.gap)));
    cards.forEach((item, index) => {
      const column = index % across, row = Math.floor(index / across);
      out.push({ id: item.id, item, type: "card", x: column * (CARD.w + CARD.gap) + CARD.w / 2, z: z + row * (CARD.d + CARD.gap) + CARD.d / 2, w: CARD.w, d: CARD.d, h: CARD.h });
    });
    if (cards.length) z += Math.ceil(cards.length / across) * (CARD.d + CARD.gap) - CARD.gap + (shapes.length ? BETWEEN : 0);
    // The shapes, in rows across the tray's middle, each at its own size; a row that is full goes on below.
    let x = 0, rowDepth = 0, row = [];
    const centre = () => {
      const used = x - BETWEEN;
      for (const entry of row) entry.x += Math.max(0, (inside - used) / 2);
    };
    for (const { item, shape } of shapes) {
      if (x > 0 && x + shape.w > inside) { centre(); x = 0; z += rowDepth + BETWEEN; rowDepth = 0; row = []; }
      const entry = { id: item.id, item, type: "shape", shape, x: x + shape.w / 2, z: z + shape.d / 2, w: shape.w, d: shape.d, h: shape.h };
      out.push(entry);
      row.push(entry);
      x += shape.w + BETWEEN;
      rowDepth = Math.max(rowDepth, shape.d);
    }
    if (shapes.length) {
      centre();
      z += rowDepth;
    }
    // Its name, in a strip along its front, where no shape standing in it can hide it.
    const lines = nameLines(group.label), head = headOf(lines);
    return { out, depth: z + 0.9 + head, head, lines };
  };
  // A row of trays, centred, as deep as its deepest tray, behind what is placed already.
  let front = 0;
  const place = (row) => {
    const filled = row.map((group) => ({ group, width: need(group), ...fill(group, need(group)) }));
    const depth = Math.max(...filled.map((tray) => tray.depth));
    let left = -widthOf(row) / 2;
    for (const tray of filled) {
      const back = front - depth;
      trays.push({ group: tray.group.id, label: tray.group.label, lines: tray.lines, head: tray.head, x: left + tray.width / 2, z: back + depth / 2, w: tray.width, d: depth });
      for (const entry of tray.out) placed.push({ ...entry, group: tray.group.id, x: left + TRAY.pad + entry.x, z: back + entry.z, y: TRAY.h });
      left += tray.width + TRAY.gap;
    }
    front -= depth + TRAY.gap;
  };
  // The small trays, in rows from the front.
  for (const row of rows) place(row);
  // The units of the law inventory: one tray as wide as the rows, behind them.
  for (const group of wide) {
    const tray = fill(group, fullWidth);
    const back = front - tray.depth;
    trays.push({ group: group.id, label: group.label, lines: tray.lines, head: tray.head, x: 0, z: back + tray.depth / 2, w: fullWidth, d: tray.depth });
    for (const entry of tray.out) placed.push({ ...entry, group: group.id, x: -fullWidth / 2 + TRAY.pad + entry.x, z: back + entry.z, y: TRAY.h });
    front -= tray.depth + TRAY.gap;
  }
  // The trays that stand behind (the vault's): rows of their own at the very back, where nothing stands behind them to be hidden.
  for (const row of backRows) place(row);
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

/**
 * The shelf of a species' organelles (schema/MACHINE_CATALOGUE.md, "Organelles"): a plank behind the bench, at the bench's one
 * scale, its organelles standing on it side by side with their fronts in one line, in the catalogue's order. Each organelle
 * comes with the room it takes (`w` across, `d` deep, `h` tall, in the view's units); one with no size in hand is a card of the
 * shelf's own size, the same for all, not to scale. Before the organelles a strip is left free: the loupe stands there.
 *
 * The small ones (`SHELF.small.um` at their longest, or less: a mitochondrion, a lysosome, a vesicle) stand on a plank of their
 * own between the bench and the shelf, nearer the bench, where a stop of their own frames them (asked for on 20 November 2026:
 * on the shelf beside a nucleus they were a few pixels across). Each item says which plank it stands on (`plank`).
 */
export const SHELF = { gap: 80, front: 420, between: 160, side: 160, back: 120, h: 12, card: { w: 300, d: 90, h: 6 }, small: { um: 1.5, gap: 50, front: 60, between: 42, side: 40, back: 60 } };
/** Whether an organelle with its room stands on the small plank: it has a size, and is no longer than `SHELF.small.um` at its longest. */
export const isSmall = (organelle) => organelle.w > 0 && Math.max(organelle.w, organelle.h, organelle.d) * UNIT_NM <= SHELF.small.um * 1000;
export function shelfOf(organelles, bounds) {
  // One plank's organelles side by side, centred across, their fronts on the line `front`.
  const row = (list, front, between, plank) => {
    const items = [];
    let x = 0;
    for (const organelle of list) {
      const card = !(organelle.w > 0);
      const w = card ? SHELF.card.w : organelle.w, d = card ? SHELF.card.d : organelle.d, h = card ? SHELF.card.h : organelle.h;
      items.push({ ...organelle, type: card ? "card" : "shape", plank, w, d, h, x: x + w / 2, z: front - d / 2, y: 0 });
      x += w + between;
    }
    const width = Math.max(0, x - between);
    for (const item of items) item.x -= width / 2;
    return { items, width, deepest: Math.max(0, ...items.map((item) => item.d)), tallest: Math.max(1, ...items.map((item) => item.h)) };
  };
  const smallList = organelles.filter(isSmall), largeList = organelles.filter((organelle) => !isSmall(organelle));
  let small = null, behind = bounds.minZ;
  if (smallList.length) {
    const s = SHELF.small, plankFront = bounds.minZ - s.gap, front = plankFront - s.front;
    const made = row(smallList, front, s.between, "small");
    const minZ = front - made.deepest - s.back;
    const plank = { x: 0, z: (plankFront + minZ) / 2, w: made.width + 2 * s.side, d: plankFront - minZ };
    small = { items: made.items, plank, front, bounds: { minX: -plank.w / 2, maxX: plank.w / 2, minZ, maxZ: plankFront, maxY: made.tallest } };
    behind = minZ;
  }
  const plankFront = behind - SHELF.gap, front = plankFront - SHELF.front;
  const made = row(largeList, front, SHELF.between, "shelf");
  const minZ = front - made.deepest - SHELF.back;
  const plank = { x: 0, z: (plankFront + minZ) / 2, w: made.width + 2 * SHELF.side, d: plankFront - minZ };
  return { items: [...made.items, ...(small?.items || [])], plank, front, small, bounds: { minX: -plank.w / 2, maxX: plank.w / 2, minZ, maxZ: plankFront, maxY: made.tallest } };
}
