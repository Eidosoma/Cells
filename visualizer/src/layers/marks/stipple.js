// stipple: on a piece of one membrane, plus and minus marks at its two faces, as many as
// the charge the membrane's voltage stands for on a piece of that size. The charge is
// capacitance times voltage; one sign sits at the inner face and as much of the other at
// the outer face, and none away from them.
//
// How many marks there are is worked out; where each mark sits is illustration, and the
// legend says so. A mark keeps its place for as long as it is drawn: when the charge
// falls, the marks drawn last go first, and nothing moves.

import * as THREE from "../../three.js";
import { membraneCharge, largest, membranesOf } from "../membrane.js";

export const MOST = 160; // the most marks drawn at one face
const WORTHS = [1, 2, 5, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000, 10000];
const SIZE = { quiet: 0.05, bold: 0.062 }; // half the length of a mark's bar, in the piece's units
const BAR = { quiet: 0.022, bold: 0.03 }; // the width of a mark's bar
const OPACITY = { quiet: 0.8, bold: 0.96 };
const LIFT = 0.1; // how far from a face its marks stand: one thin layer, as the charge itself is

/** How many charges one mark stands for, so that the largest count of a run stays drawable. */
export function worthFor(most) {
  return WORTHS.find((worth) => most / worth <= MOST) ?? WORTHS[WORTHS.length - 1];
}

/** How many marks stand at each face for a count of charges on the piece. */
export function marksFor(charges, worth) {
  return Math.min(MOST, Math.round(charges / worth));
}

/**
 * The places of the marks at one face, the same every time: a sequence that fills the
 * face evenly however many of its places are used, so that a mark never has to move.
 * `free(x, y, z)` says whether a place is clear of the close-up's own words.
 */
export function spots(piece, side, free = () => true) {
  // Roberts' sequence in two dimensions: each new place falls in the widest gap left, so the
  // layer is even whether ten of its places are used or all of them.
  const g = 1.324717957244746, steps = [1 / g, 1 / (g * g)];
  const out = [], seed = side > 0 ? 0.5 : 0.137;
  const y = side * (piece.thick / 2 + LIFT);
  for (let n = 1; out.length < MOST && n < MOST * 6; n++) {
    const [u, v] = steps.map((step) => (seed + n * step) % 1);
    const x = (u - 0.5) * (piece.width - 0.24), z = (v - 0.5) * (piece.depth - 0.16);
    if (free(x, y, z)) out.push([x, y, z]);
  }
  return out;
}

export const stipple = {
  name: "stipple",
  channels: ["surface"],
  lives_on: ["membrane"],
  surface: "membrane",

  /**
   * context: surface (the close-up's piece), run, layer (its `piece` gives the size of the
   * piece of membrane the marks are counted on, in nanometres), fed (what the run feeds the
   * rule `charge` with), membrane, strength, colours ({ ink }), memo.
   */
  create({ surface, run, layer, fed, membrane, strength = "quiet", colours, memo = (key, make) => make() }) {
    const reader = membraneCharge(run, fed);
    const { piece, order } = surface;
    const size = { width_nm: layer.piece?.width_nm ?? 100, depth_nm: layer.piece?.depth_nm ?? 25 };
    const area = size.width_nm * size.depth_nm * 1e-6; // square micrometres
    // One worth for a mark over the whole run: the largest charge of any membrane at any valid record decides it.
    const worth = memo("stipple-worth", () => worthFor(largest(run, membranesOf(run).ids.length, (step, index) => reader.at(step, index).per_um2) * area));

    const material = new THREE.MeshBasicMaterial({ transparent: true, opacity: OPACITY[strength], depthTest: false, depthWrite: false, side: THREE.DoubleSide });
    material.color.copy(colours.ink);
    const plusShape = cross(true), minusShape = cross(false);
    const mesh = (geometry) => {
      const item = new THREE.InstancedMesh(geometry, material, MOST);
      item.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
      item.count = 0;
      item.renderOrder = order.marks;
      item.frustumCulled = false;
      item.userData.unpickable = true;
      surface.root.add(item);
      return item;
    };
    const plus = mesh(plusShape), minus = mesh(minusShape);
    const places = { outer: spots(piece, 1, surface.free), inner: spots(piece, -1, surface.free) };
    let half = SIZE[strength], bar = BAR[strength], last = null;
    const matrix = new THREE.Matrix4(), position = new THREE.Vector3(), turn = new THREE.Quaternion(), scale = new THREE.Vector3();
    const put = (item, list, count) => {
      for (let k = 0; k < count; k++) {
        position.set(...list[k]);
        scale.set(half, half, 1);
        item.setMatrixAt(k, matrix.compose(position, turn, scale));
      }
      item.count = count;
      item.instanceMatrix.needsUpdate = true;
    };

    return {
      worth,
      piece: size,
      area,
      /** The charge at the record last drawn, with how many marks stand at each face; null at a record that is not valid. */
      get readings() {
        return last;
      },
      at(step) {
        const reading = reader.at(step, membrane);
        return { ...reading, on_piece: reading.per_um2 * area, marks: marksFor(reading.per_um2 * area, worth), worth };
      },
      update(step, valid) {
        last = valid ? this.at(step) : null;
        const count = last ? Math.min(last.marks, places.outer.length, places.inner.length) : 0;
        // The cell's own sign sits at the inner face; the outer face carries as much of the other.
        const inside = last?.inside === "plus" ? plus : minus, outside = inside === plus ? minus : plus;
        // The marks at the inner face lie under the membrane and are seen through its glass; those at the outer face lie over it.
        inside.renderOrder = order.under;
        outside.renderOrder = order.marks;
        // The bar of a mark keeps its width whatever the mark's size: the shapes are built for the size in use.
        put(inside, places.inner, last?.inside ? count : 0);
        put(outside, places.outer, last?.inside ? count : 0);
      },
      /** The legend's line: what one mark stands for, and that its place is illustration. */
      keys(write) {
        const charges = worth === 1 ? "one charge" : `${write(worth, 0)} charges`;
        return [{ key: "charges", text: `Each mark is ${charges} on a piece of membrane ${write(size.width_nm, 0)} nm by ${write(size.depth_nm, 0)} nm. Where a mark sits is illustration; so is the membrane's thickness` }];
      },
      /** The same in a line for the close-up itself. */
      note(write) {
        return `Plus and minus: each mark is ${worth === 1 ? "one charge" : `${write(worth, 0)} charges`} on a piece ${write(size.width_nm, 0)} nm by ${write(size.depth_nm, 0)} nm. Where a mark sits is illustration.`;
      },
      setStrength(next) {
        half = SIZE[next];
        bar = BAR[next];
        material.opacity = OPACITY[next];
        for (const [item, sign] of [[plus, true], [minus, false]]) {
          item.geometry.dispose();
          item.geometry = cross(sign, bar / half);
        }
      },
      setColours(next) {
        material.color.copy(next.ink);
      },
      dispose() {
        for (const item of [plus, minus]) {
          surface.root.remove(item);
          item.geometry.dispose();
          item.dispose?.();
        }
        material.dispose();
      },
    };

    /** A plus or a minus of half-length 1, its bars `thick` wide: flat, facing the viewer. */
    function cross(isPlus, thick = BAR[strength] / SIZE[strength]) {
      const t = thick / 2;
      const positions = [-1, -t, 0, 1, -t, 0, 1, t, 0, -1, t, 0], index = [0, 1, 2, 0, 2, 3];
      if (isPlus) {
        // The upright bar in two pieces, above and below the level one, so that no part is drawn twice.
        positions.push(-t, t, 0, t, t, 0, t, 1, 0, -t, 1, 0, -t, -1, 0, t, -1, 0, t, -t, 0, -t, -t, 0);
        index.push(4, 5, 6, 4, 6, 7, 8, 9, 10, 8, 10, 11);
      }
      const geometry = new THREE.BufferGeometry();
      geometry.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
      geometry.setIndex(index);
      return geometry;
    }
  },
};
