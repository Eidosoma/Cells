// Where everything of the Laws library stands, in the scene's units: the wall of bars by
// family, the frames with their slot rows, and the strip of older families. Numbers only, no
// drawing, so that the tests can hold the picture to the list without a renderer.

export const WIDE = {
  bar: { w: 1.3, d: 0.22, col: 1.5, gap: 0.32, height: 9, pitchMax: 0.3, z: -3, base: 7.8 },
  frames: { z: 4, height: 6.4 },
  older: { z: 7.4, pitch: 0.24, w: 0.16, h: 0.42 },
};

/** The frames' boxes and slots, laid out from the list: each slot names the piece its row names. */
function frameBoxes(library, narrow) {
  const racks = library.racks;
  const inner = racks.find((frame) => frame.kind === "inner model");
  const composite = racks.find((frame) => frame.kind === "composite");
  const compositions = racks.filter((frame) => frame.kind === "composition");
  const H = WIDE.frames.height;
  // Wide: @3, the composite and a column of the compositions, side by side. Narrow: one above another.
  const spots = narrow
    ? [
        { frame: inner, x: 0, y: H + 0.9 + 2.3 + 0.9, w: 9.4, h: H },
        { frame: composite, x: 0, y: 2.3 + 0.9, w: 9.4, h: H },
        ...compositions.map((frame, index) => ({ frame, x: (index - (compositions.length - 1) / 2) * 3.15, y: 0, w: 3.0, h: 2.3 })),
      ]
    : [
        { frame: inner, x: -7.4, y: 0, w: 10, h: H },
        { frame: composite, x: 2.5, y: 0, w: 8, h: H },
        ...compositions.map((frame, index) => ({ frame, x: 9.9, y: (compositions.length - 1 - index) * ((H + 0.2) / compositions.length), w: 5.2, h: (H - 0.2 * (compositions.length - 1)) / compositions.length })),
      ];
  return spots
    .filter((spot) => spot.frame)
    .map((spot) => {
      const { frame, x, y, w, h } = spot;
      const left = x - w / 2, top = y + h;
      const box = { id: frame.id, kind: frame.kind, x, y, w, h, z: WIDE.frames.z, rows: [], block: null };
      let cursor = top - 0.35;
      if (frame.inner) {
        const bh = frame.kind === "composite" ? 0.46 : 0.36;
        box.block = { id: frame.inner, x, y: cursor - bh / 2, w: w - 0.5, h: bh };
        cursor -= bh + 0.22;
      }
      const rows = frame.rows || [];
      if (frame.kind === "inner model") {
        const rowH = (cursor - y - 0.25) / Math.max(1, rows.length);
        const labelW = narrow ? 2.4 : 2.7, slotW = narrow ? 0.92 : 1.02, slotH = Math.min(0.42, rowH * 0.62);
        rows.forEach((row, r) => {
          const cy = cursor - rowH * (r + 0.5);
          const slots = row.pieces.map((id, index) => ({ id, row: r, index, x: left + labelW + index * (slotW + 0.12) + slotW / 2, y: cy, w: slotW, h: slotH }));
          const next = row.next_code !== undefined ? { x: left + labelW + row.pieces.length * (slotW + 0.12) + slotW / 2, y: cy, w: slotW, h: slotH } : null;
          box.rows.push({ label: row.label, x: left + 0.3, y: cy, slots, next });
        });
      } else {
        const columns = frame.kind === "composite" ? 2 : Math.max(1, Math.min(2, rows[0]?.pieces.length || 1));
        const pieces = rows.flatMap((row, r) => row.pieces.map((id, index) => ({ id, row: r, index })));
        const lines = Math.ceil(pieces.length / columns) || 1;
        const pitch = Math.min(0.56, (cursor - y - 0.25) / lines);
        const slotW = (w - 0.6 - (columns - 1) * 0.2) / columns, slotH = Math.min(0.4, pitch * 0.72);
        const slots = pieces.map((slot, n) => ({ ...slot, x: left + 0.3 + (n % columns) * (slotW + 0.2) + slotW / 2, y: cursor - pitch * (Math.floor(n / columns) + 0.5), w: slotW, h: slotH }));
        box.rows.push({ label: rows[0]?.label || "", x: left + 0.3, y: cursor, slots, next: null });
      }
      return box;
    });
}

/**
 * The whole picture's places. `size` (a test of size only) adds empty slots to the wall in
 * today's proportions; `narrow` stacks the wall in three bands of five families and the
 * frames one above another, for a tall screen.
 */
export function layoutOf(library, { size = 0, narrow = false } = {}) {
  const columns = library.columns(size);
  const frames = frameBoxes(library, narrow);
  const top = Math.max(...frames.map((frame) => frame.y + frame.h));
  const { w, d, col, gap, height, pitchMax } = WIDE.bar;
  const perBand = narrow ? 5 : columns.length;
  const bands = Math.ceil(columns.length / perBand);
  const bandHeight = narrow ? 4.4 : height;
  const tallest = Math.max(1, ...columns.map((column) => column.pieces.length + 1));
  const pitch = Math.min(pitchMax, bandHeight / tallest);
  const barH = pitch * 0.78;
  const base = top + (narrow ? 1.6 : 1.4);
  const z = narrow ? -1.2 : WIDE.bar.z;
  const bars = [], heads = [];
  columns.forEach((column, n) => {
    const band = Math.floor(n / perBand), place = n % perBand;
    const inBand = Math.min(perBand, columns.length - band * perBand);
    const x = (place - (inBand - 1) / 2) * (col + gap);
    const y0 = base + (bands - 1 - band) * (bandHeight + 1.6);
    // The older families' laws stand on their own part of the shelf, above a gap, and narrower: marked as in an older family.
    let lift = 0, before = false;
    column.pieces.forEach((piece, j) => {
      const older = piece?.registry === "an older family" || piece?.registry === "no registry";
      if (older && !before && j > 0) lift += pitch * 0.9;
      before = before || older;
      bars.push({ id: piece?.id ?? null, family: column.family.id, older, x, y: y0 + lift + j * pitch + barH / 2, z, w: older ? w * 0.7 : w, h: barH, d });
    });
    heads.push({ family: column.family, shelf: column.family.shelf, x, y: y0 - 0.5, top: y0 + lift + column.pieces.length * pitch, band });
  });
  const wallWidth = perBand * (col + gap) - gap;
  const wall = { x: 0, y: base - 0.9, w: wallWidth + 1.4, h: bands * (bandHeight + 1.6) + 0.2, z: z - 0.32 };
  const older = library.older.map((frame, index, all) => ({ id: frame.id, x: (index - (all.length - 1) / 2) * (narrow ? 0.09 : WIDE.older.pitch), y: WIDE.older.h / 2 - 0.05, z: WIDE.older.z }));
  const spanX = Math.max(wall.w, ...frames.map((frame) => Math.abs(frame.x) * 2 + frame.w));
  return { bars, heads, frames, wall, older, pitch, bounds: { minX: -spanX / 2, maxX: spanX / 2, minY: -0.6, maxY: wall.y + wall.h + 1.4, minZ: z - 1, maxZ: WIDE.older.z + 1 } };
}
