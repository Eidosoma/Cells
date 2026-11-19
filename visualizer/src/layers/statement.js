// Where the picture's own statement of a layer stands (schema/QUANTITY_LAYERS.md, rules 3,
// 6 and 11: what one bead stands for and what time it keeps, "Invented numbers · no run of Cells' engine",
// "Illustration: not a run"). It is on the picture for as long as the layer shows, so no
// card that lies over the picture (the legend, a panel, a view's card) may cut it.
//
// A label follows a point of the scene and stands just above it, in the middle (core/labels.js).
// Nothing here draws: these work out where on the screen the label has room, and where its
// point must then lie.

/**
 * Where a box `wide` pixels across fits on the rows from `top` to `top + tall`, clear of the
 * cards in `blocked` ([{ left, top, right, bottom }], in pixels of the window) and inside a
 * window `width` across: the middle of the box, as near to `wanted` as it can be, or null
 * where no free stretch of those rows is wide enough.
 */
export function fitOnRow({ width, blocked = [], top, tall, wide, wanted, margin = 6 }) {
  let free = [[margin, width - margin]];
  for (const rect of blocked) {
    if (rect.bottom <= top - margin || rect.top >= top + tall + margin) continue;
    free = free.flatMap(([from, to]) => [[from, Math.min(to, rect.left - margin)], [Math.max(from, rect.right + margin), to]]);
  }
  let best = null;
  for (const [from, to] of free) {
    if (to - from < wide) continue;
    const middle = Math.min(Math.max(wanted, from + wide / 2), to - wide / 2);
    if (best === null || Math.abs(middle - wanted) < Math.abs(best - wanted)) best = middle;
  }
  return best;
}

/**
 * A label that follows the scene point `home`, kept whole: the point its label should
 * follow instead, written into `out`, so that the label (`wide` by `tall`, standing `lift`
 * pixels above its point) is cut by no card. It keeps its row and moves along it as little
 * as will do; where the row has no room it moves up, row by row, as far as `reach` pixels.
 * Where it has room at home, or none anywhere, `out` is `home`. `stage` gives the window's
 * size, the camera and `project(point, out)`: pixels across and down, and the depth.
 */
export function clearOf({ stage, blocked = [], home, wide, tall, lift = 0, out, reach = 240, margin = 6 }) {
  stage.camera.updateMatrixWorld?.(); // the camera may have moved in this frame, and its matrices are brought up to date only when the frame is drawn
  stage.project(home, out);
  const across = out.x, down = out.y, depth = out.z;
  if (!(depth > -1 && depth < 1) || !(stage.width > 0) || !(stage.height > 0)) return out.copy(home);
  for (let up = 0; up <= reach; up += 8) {
    const middle = fitOnRow({ width: stage.width, blocked, top: down - up - lift - tall, tall, wide, wanted: across, margin });
    if (middle === null) continue;
    if (up === 0 && Math.abs(middle - across) < 0.5) break; // it has room where it is
    return out.set((middle / stage.width) * 2 - 1, 1 - ((down - up) / stage.height) * 2, depth).unproject(stage.camera);
  }
  return out.copy(home);
}
