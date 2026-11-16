// wedge: on every junction, the difference of a saved level between the two cells it
// joins, drawn as a wedge that points down the drop and is as wide as the drop is large.
// A wedge is the difference of two saved numbers, not a current: it never moves.
//
// Where the run saved more about a junction, the wedge says it: hollow where the
// junction's gate is under half open, and two bars in place of a wedge where no junction
// has formed. Where the run did not save those, every wedge is solid, and the legend says so.
//
// A sign stands out from the top edge of the higher of the two cells, over the seam and the
// lower cell, pointing at it: from above nothing hides it, and round a cell that stands alone
// six of them do not run into one another. It is drawn in the page's ink or in the page's
// ground, whichever stands out more from the colour the lower cell has at that moment, so it
// reads over a cell of any colour, in both themes.

import * as THREE from "../../three.js";
import { difference } from "../derive.js";
import { roundUp } from "../scale.js";

export const FLOOR = 0.04; // a drop under this share of the scale is not drawn
export const SHUT = 0.5; // a gate under this is drawn as shut (hollow)
export const ABSENT = 0.02; // a junction formed less than this is drawn as absent (two bars)
const SIZE = { quiet: 1, bold: 1.45 };

/**
 * What is drawn on one junction, from the saved values at its two ends:
 * null (a drop too small to draw), a wedge ({ kind: "solid" | "hollow", share, towards })
 * or a break ({ kind: "break" }). `towards` is the end the wedge points at: the lower one.
 */
export function dropAt({ here, there, across = null, full, gate = null, formed = null }) {
  // A run that kept the junction's own voltage gives it (`across`); otherwise it is the
  // difference of the two ends' saved levels.
  const drop = across !== null ? across : difference(here, there);
  const size = Math.abs(drop);
  if (!Number.isFinite(size) || !(size >= FLOOR * full)) return null;
  if (formed !== null && formed < ABSENT) return { kind: "break", drop };
  return { kind: gate !== null && gate < SHUT ? "hollow" : "solid", drop, share: Math.min(1, size / full), towards: drop > 0 ? "there" : "here" };
}

/** The largest drop across any junction at any valid record of the run: what the wedge's full width stands for, before rounding. */
export function fullDrop(run, dropOf, links) {
  let most = 0;
  for (let step = 0; step < run.count; step++) {
    if (!run.isValid(step)) continue;
    for (const link of links) most = Math.max(most, Math.abs(dropOf(step, link)));
  }
  return most;
}

export const wedge = {
  name: "wedge",
  channels: ["links"],
  lives_on: ["junction"],

  /**
   * context (see ./index.js). `fed.source` is the saved record: a level on the cells, of
   * which the difference across each junction is taken, or the junctions' own saved voltage,
   * which is read as it is (its declared sign says which end is the higher when it is
   * positive). `fed.extras` name, by role, the junctions' saved gate and how far each has
   * formed, where the run saved them. colours: { ink, ground }, the page's text colour and
   * its background.
   */
  create({ surface, run, fed, shown: shownOf, strength = "quiet", colours }) {
    const links = surface.links;
    const record = run.records.get(fed.source.id);
    const shown = shownOf(record);
    const own = fed.source.lives_on === "junction";
    const turn = fed.source.sign?.high === "second" ? -1 : 1;
    const extra = (role) => {
      const item = fed.extras.find((entry) => entry.role === role);
      return item ? run.records.get(item.record) || null : null;
    };
    const gate = extra("gate"), formed = extra("formed");
    // The drop from a link's first cell to its second, at one record.
    const dropOf = own ? (step, link) => record.at(step, link.link) * turn : (step, link) => difference(record.at(step, link.a), record.at(step, link.b));
    const full = roundUp(fullDrop(run, dropOf, links) * shown.factor) / shown.factor;
    const group = new THREE.Group();
    group.userData.unpickable = true;
    const material = new THREE.MeshBasicMaterial({ transparent: true, opacity: 0.94, depthWrite: false, side: THREE.DoubleSide });
    const shapes = { solid: triangle(), hollow: outline(), break: bars() };
    const meshes = Object.fromEntries(
      Object.entries(shapes).map(([kind, geometry]) => {
        const mesh = new THREE.InstancedMesh(geometry, material, Math.max(1, links.length));
        mesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
        mesh.setColorAt(0, colours.ink);
        mesh.frustumCulled = false;
        mesh.userData.unpickable = true;
        mesh.renderOrder = 4;
        group.add(mesh);
        return [kind, mesh];
      })
    );
    surface.root.add(group);

    // Where each link's sign lies: the middle of the seam, the way from its first cell to its
    // second, how long the seam is and how wide the gap between the two cells.
    const frames = links.map((link) => {
      const [a0, a1, b1, b0] = link.points;
      const ax = (a0[0] + a1[0]) / 2, ay = (a0[1] + a1[1]) / 2, bx = (b0[0] + b1[0]) / 2, by = (b0[1] + b1[1]) / 2;
      let dx = bx - ax, dy = by - ay;
      const gap = Math.hypot(dx, dy) || 1;
      dx /= gap;
      dy /= gap;
      return { x: (ax + bx) / 2, y: (ay + by) / 2, dx, dy, gap, edge: Math.hypot(a1[0] - a0[0], a1[1] - a0[1]) };
    });

    let size = SIZE[strength], ink = colours.ink.clone(), ground = colours.ground.clone();
    // Ink or ground: the one that stands out more from a cell's colour of the moment.
    const tops = surface.geometry.attributes.color.array;
    const light = (r, g, b) => 0.2126 * r + 0.7152 * g + 0.0722 * b;
    const apart = (one, other) => (Math.max(one, other) + 0.05) / (Math.min(one, other) + 0.05);
    const toneOn = (cell) => {
      const at = cell.start * 3, here = light(tops[at], tops[at + 1], tops[at + 2]);
      return apart(here, light(ink.r, ink.g, ink.b)) >= apart(here, light(ground.r, ground.g, ground.b)) ? ink : ground;
    };
    const matrix = new THREE.Matrix4(), position = new THREE.Vector3(), quaternion = new THREE.Quaternion(), scale = new THREE.Vector3(), up = new THREE.Vector3(0, 1, 0);
    const hidden = new THREE.Matrix4().makeScale(0, 0, 0);
    const counts = { solid: 0, hollow: 0, break: 0 };
    /** Lay a sign flat: its own +x along the way given, its middle `along` that way from the seam's middle. */
    const put = (mesh, index, frame, sign, along, length, width, height) => {
      position.set(frame.x + frame.dx * sign * along, height, frame.y + frame.dy * sign * along);
      quaternion.setFromAxisAngle(up, -Math.atan2(frame.dy * sign, frame.dx * sign));
      scale.set(length, 1, width);
      mesh.setMatrixAt(index, matrix.compose(position, quaternion, scale));
    };

    return {
      record,
      full,
      counts,
      get floor() {
        return FLOOR * full;
      },
      update(step, valid) {
        counts.solid = counts.hollow = counts.break = 0;
        const lift = surface.pitch * 0.03;
        links.forEach((link, index) => {
          const frame = frames[index];
          const drawn = valid ? dropAt({ across: dropOf(step, link), full, gate: gate ? gate.at(step, link.link) : null, formed: formed ? formed.at(step, link.link) : null }) : null;
          for (const mesh of Object.values(meshes)) mesh.setMatrixAt(index, hidden);
          if (!drawn) return;
          counts[drawn.kind] += 1;
          // The sign starts at the higher cell's edge, at the height of its top, and points out over the lower one.
          const sign = drawn.drop > 0 ? 1 : -1; // the way from the higher cell to the lower, along the link
          const high = sign > 0 ? surface.cells[link.a] : surface.cells[link.b];
          const low = sign > 0 ? surface.cells[link.b] : surface.cells[link.a];
          const mesh = meshes[drawn.kind];
          if (drawn.kind === "break") {
            // Two bars across the seam itself.
            put(mesh, index, frame, sign, 0, surface.pitch * 0.2 * Math.min(1.25, size), frame.edge * 0.46, high.height + lift);
          } else {
            const length = surface.pitch * (0.2 + 0.14 * drawn.share) * Math.min(1.25, size);
            const width = frame.edge * (0.2 + 0.5 * drawn.share) * Math.min(1.15, size);
            put(mesh, index, frame, sign, -frame.gap / 2 + BASE * length, length, width, high.height + lift);
          }
          mesh.setColorAt(index, toneOn(low));
        });
        for (const mesh of Object.values(meshes)) {
          mesh.instanceMatrix.needsUpdate = true;
          if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true;
        }
      },
      /** The legend's lines for what is drawn: the sizes, and what a hollow wedge and two bars mean where the run saved them. */
      keys(write) {
        const unit = shown.unit ? ` ${shown.unit}` : "";
        const lines = [{ key: "wedge", text: `A wedge points down the drop; the widest stands for ${write(full * shown.factor, 0)}${unit}. Drops under ${write(FLOOR * full * shown.factor, 1)}${unit} are not drawn` }];
        if (gate) lines.push({ key: "wedge-hollow", text: "Hollow: the junction's gate is under half open" });
        if (formed) lines.push({ key: "break", text: "Two bars: the cells differ, and no junction has formed between them" });
        return lines;
      },
      setStrength(next) {
        size = SIZE[next];
      },
      setColours(next) {
        ink = next.ink.clone();
        ground = next.ground.clone();
      },
      dispose() {
        surface.root.remove(group);
        material.dispose();
        for (const geometry of Object.values(shapes)) geometry.dispose();
      },
    };
  },
};

// A wedge's own shape: its point at x = 1 - BASE, its base at x = -BASE across z.
const BASE = 0.42;

/** A wedge lying flat: its point at +x, its base across z. */
function triangle() {
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.Float32BufferAttribute([1 - BASE, 0, 0, -BASE, 0, -0.5, -BASE, 0, 0.5], 3));
  geometry.setIndex([0, 1, 2]);
  return geometry;
}

/** The same wedge as an outline: the band between it and a smaller one inside it. */
function outline() {
  const outer = [[1 - BASE, 0], [-BASE, -0.5], [-BASE, 0.5]];
  // The inner wedge: the outer one drawn towards its middle, so that the band is of even width to the eye.
  const middle = [(1 - 3 * BASE) / 3 + 0, 0];
  const inner = outer.map(([x, z]) => [middle[0] + (x - middle[0]) * 0.5, middle[1] + (z - middle[1]) * 0.5]);
  const positions = [...outer, ...inner].flatMap(([x, z]) => [x, 0, z]);
  const index = [];
  for (let k = 0; k < 3; k++) {
    const next = (k + 1) % 3;
    index.push(k, next, 3 + next, k, 3 + next, 3 + k);
  }
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
  geometry.setIndex(index);
  return geometry;
}

/** Two short bars lying flat, side by side along x, each across z: a break in a junction. */
function bars() {
  const positions = [], index = [];
  for (const [k, x] of [-0.3, 0.3].entries()) {
    const half = 0.14;
    positions.push(x - half, 0, -0.5, x + half, 0, -0.5, x + half, 0, 0.5, x - half, 0, 0.5);
    index.push(k * 4, k * 4 + 1, k * 4 + 2, k * 4, k * 4 + 2, k * 4 + 3);
  }
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
  geometry.setIndex(index);
  return geometry;
}
