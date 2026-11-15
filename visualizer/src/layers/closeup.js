// The close-up: a piece of one chosen cell's membrane, drawn beside the sheet and tied to
// its cell (schema/QUANTITY_LAYERS.md, rule 7). The layers that live on a membrane draw on
// it: arrows through it, marks at its two faces.
//
// It is a callout in the scene. It keeps one size on the screen and always faces the
// viewer, a little from above so that its outer face shows; it stands in the free part of
// the window, above its cell where there is room; and a tie joins it to the cell it is a
// piece of. Up is out of the cell: the outside is above the membrane, the inside below.
//
// The membrane is drawn in the look the page has for membranes: lit glass in the
// membrane's own colour. What the run does not give is not drawn to scale and is said:
// the membrane's thickness is the drawing's.

import * as THREE from "../three.js";
import { soften, roundedSlab } from "../core/materials.js";

// The piece, in its own units: x along it, y through it (up is outside), z towards the viewer.
// `reach` is how far a full arrow stands out from a face; `front` is the plane of its near
// edge, where the membrane is seen in section and the arrows cross it.
export const PIECE = { width: 3.6, depth: 0.9, thick: 0.3, reach: 1.05, front: 0.9 / 2 + 0.012 };
export const TILT = 0.26; // radians: how far the piece leans its outer face towards the viewer
const COS = Math.cos(TILT), SIN = Math.sin(TILT);
// How high a point of the piece stands on the card, as the viewer sees it.
const seen = (y, z) => y * COS - z * SIN;
const EDGE = seen(PIECE.thick / 2, -PIECE.depth / 2); // the far edge of the outer face: the top of the piece's outline
// The card behind the piece: its left and right edges, the room above a full arrow for the ions' names, and its foot.
const CARD = { left: -PIECE.width / 2 - 0.14, right: PIECE.width / 2 + 0.6, top: seen(PIECE.thick / 2 + PIECE.reach, PIECE.front) + 0.6, low: seen(-PIECE.thick / 2 - PIECE.reach, PIECE.front) - 0.1, foot: 0.14 };
const CARD_WIDTH = CARD.right - CARD.left;
// The order the parts are drawn in. Everything of the close-up is drawn after the sheet (`group`), and nothing
// is hidden by depth: the card, the marks under the membrane, the glass, the marks over it, then the arrows in front.
// `forms` and `beads` are kept for what stands through the membrane and crosses in it (channel populations, pumps and
// the tokens of their rates): forms are seen through the glass, beads pass in front of everything.
export const ORDER = { group: 20, tie: 20, card: 21, under: 22, forms: 23, glass: 24, marks: 25, arrows: 26, beads: 27 };
// The two words that say which side is which stand over the piece's left end; no mark is put under them.
const WORDS = { x: -PIECE.width / 2 + 0.38, y: EDGE + 0.1, clear: { left: -PIECE.width / 2 - 0.2, right: -PIECE.width / 2 + 0.82, near: EDGE + 0.02, far: EDGE + 0.4 } };
const MARGIN = 10; // pixels kept between the card and the edge of the free part of the window
// The close-up is drawn nearly flat along the line of sight: what leans towards the viewer keeps its place on the card
// wherever on the screen the card stands, and the names stay over their arrows.
const DEPTH = 0.2;
const GAP = 26; // pixels between the cell and the card

/**
 * The largest rectangle of the window that no panel covers: { left, top, right, bottom }.
 * `blocked` are the panels' rectangles; `top` is the height of the bar along the top.
 */
export function freeRect(width, height, blocked = [], top = 0) {
  const clampX = (value) => Math.min(width, Math.max(0, value)), clampY = (value) => Math.min(height, Math.max(top, value));
  const boxes = blocked.map((box) => ({ left: clampX(box.left), right: clampX(box.right), top: clampY(box.top), bottom: clampY(box.bottom) })).filter((box) => box.right - box.left > 1 && box.bottom - box.top > 1);
  const xs = [...new Set([0, width, ...boxes.flatMap((box) => [box.left, box.right])])].sort((a, b) => a - b);
  const ys = [...new Set([top, height, ...boxes.flatMap((box) => [box.top, box.bottom])])].sort((a, b) => a - b);
  let best = null;
  for (let a = 0; a < xs.length; a++) {
    for (let b = a + 1; b < xs.length; b++) {
      for (let c = 0; c < ys.length; c++) {
        for (let d = c + 1; d < ys.length; d++) {
          const area = (xs[b] - xs[a]) * (ys[d] - ys[c]);
          if (best && area <= best.area) continue;
          if (boxes.some((box) => box.left < xs[b] - 0.5 && box.right > xs[a] + 0.5 && box.top < ys[d] - 0.5 && box.bottom > ys[c] + 0.5)) continue;
          best = { left: xs[a], top: ys[c], right: xs[b], bottom: ys[d], area };
        }
      }
    }
  }
  return best || { left: 0, top, right: width, bottom: height, area: width * (height - top) };
}

/**
 * Where the card stands, in pixels: { x, y, width, height, side, fits, room }. It goes above
 * its cell where there is room, below it otherwise, and is pushed into the free part of the
 * window in any case. `side` says which edge of the card the tie comes to: its bottom or its
 * top. `fits` is false where it has room on neither side and so lies over its cell; `room`
 * is then how far down the window the cell would have to stand for the card to fit above it.
 */
export function cardPlace(cell, free, width, height) {
  const lowX = free.left + MARGIN + width / 2, highX = free.right - MARGIN - width / 2;
  const lowY = free.top + MARGIN + height / 2, highY = free.bottom - MARGIN - height / 2;
  const clamp = (value, low, high) => (high < low ? (low + high) / 2 : Math.min(high, Math.max(low, value)));
  const above = cell.y - GAP - height / 2, below = cell.y + GAP + height / 2;
  const fitsAbove = above >= lowY, fitsBelow = below <= highY;
  const side = fitsAbove || !fitsBelow ? "bottom" : "top";
  const within = cell.x >= free.left && cell.x <= free.right && cell.y >= free.top && cell.y <= free.bottom;
  return {
    x: clamp(cell.x, lowX, highX), y: clamp(side === "bottom" ? above : below, lowY, highY), width, height, side,
    fits: (fitsAbove || fitsBelow) && within,
    room: { x: clamp(cell.x, lowX, highX), y: Math.min(free.bottom - 2 * MARGIN, free.top + MARGIN + height + GAP + 6) },
  };
}

export class Closeup {
  /** root: the group of the lens the close-up is added to. colours: { ink, ground, glass }. */
  constructor({ root, colours }) {
    this.root = root;
    this.group = new THREE.Group(); // faces the viewer; placed and sized anew for every frame
    this.piece = new THREE.Group(); // the piece of membrane and what the layers draw on it
    this.piece.rotation.x = TILT;
    this.group.add(this.piece);
    this.group.userData.unpickable = true;
    // A group's own order goes before its parts' when the renderer sorts: every group of the close-up has it.
    this.group.renderOrder = this.piece.renderOrder = ORDER.group;
    this.handles = [];
    this.labels = null;
    this.unitPx = 100;
    this.placed = null;
    this.captionHeight = 0;

    // The card: a plain ground behind the piece, so that it reads over a sheet of any colour.
    this.cardMaterial = new THREE.MeshBasicMaterial({ transparent: true, opacity: 0.95, depthTest: false, depthWrite: false });
    this.card = new THREE.Mesh(new THREE.PlaneGeometry(1, 1), this.cardMaterial);
    this.card.renderOrder = ORDER.card;
    this.edgeMaterial = new THREE.LineBasicMaterial({ transparent: true, opacity: 0.32, depthTest: false, depthWrite: false });
    this.edge = new THREE.LineLoop(new THREE.BufferGeometry().setAttribute("position", new THREE.Float32BufferAttribute(new Float32Array(12), 3)), this.edgeMaterial);
    this.edge.renderOrder = ORDER.card;
    this.group.add(this.card, this.edge);

    // The membrane: glass, as the page draws membranes.
    this.glassMaterial = soften(new THREE.MeshStandardMaterial({ roughness: 0.25, metalness: 0, transparent: true, opacity: 0.36, side: THREE.DoubleSide, depthWrite: false, depthTest: false }), { rim: 0.5, alphaRim: 0.5 });
    const slab = roundedSlab(PIECE.width, PIECE.depth, 0.14, 0.05);
    slab.scale(1, PIECE.thick, 1).translate(0, -PIECE.thick / 2, 0);
    this.slab = new THREE.Mesh(slab, this.glassMaterial);
    this.slab.renderOrder = ORDER.glass;
    this.piece.add(this.slab);

    // The tie to the cell: two fine bands from the cell to the card's near corners, and a faint wash between them.
    this.tieMaterial = new THREE.MeshBasicMaterial({ transparent: true, opacity: 0.6, depthTest: false, depthWrite: false, side: THREE.DoubleSide });
    this.washMaterial = new THREE.MeshBasicMaterial({ transparent: true, opacity: 0.1, depthTest: false, depthWrite: false, side: THREE.DoubleSide });
    const flat = (points, index) => new THREE.BufferGeometry().setAttribute("position", new THREE.Float32BufferAttribute(new Float32Array(points * 3), 3)).setIndex(index);
    this.tie = new THREE.Mesh(flat(8, [0, 1, 2, 0, 2, 3, 4, 5, 6, 4, 6, 7]), this.tieMaterial);
    this.wash = new THREE.Mesh(flat(3, [0, 1, 2]), this.washMaterial);
    for (const object of [this.tie, this.wash]) {
      object.renderOrder = ORDER.tie;
      object.frustumCulled = false;
      object.userData.unpickable = true;
    }
    for (const object of [this.card, this.edge, this.slab]) object.frustumCulled = false;
    this.ties = new THREE.Group(); // in the scene's own space: the tie runs from the cell to the card
    this.ties.renderOrder = ORDER.group;
    this.ties.userData.unpickable = true;
    this.ties.add(this.wash, this.tie);
    this.root.add(this.ties, this.group);
    this.setColours(colours);
    this.layout();
    // Which side is which, and what the close-up is: the run, the cell, the time, and what its numbers are worked out from.
    this.outside = this.label({ text: "Outside", at: [WORDS.x, WORDS.y, 0], kind: "closeup label-closeup-side", flat: true });
    this.inside = this.label({ text: "Inside", at: [WORDS.x, -WORDS.y, 0], kind: "closeup label-closeup-side", flat: true });
    this.inside.below(true);
    this.caption = this.label({ at: this.captionAt, kind: "closeup label-closeup-caption", flat: true });
  }

  /**
   * What a mark of a membrane draws on: the piece's own group and its measures, how to put
   * a label on it, and whether a place on it is clear of the close-up's own words.
   */
  get surface() {
    return { root: this.piece, piece: PIECE, order: ORDER, label: (spec) => this.label(spec), free: (x, y, z) => Closeup.free(x, y, z) };
  }

  /** Whether a point of the piece (in its own units) is clear of the words "Outside" and "Inside", as the viewer sees it. */
  static free(x, y, z) {
    const high = Math.abs(seen(y, z)); // how high the point stands on the card, above or below the piece's middle
    const { left, right, near, far } = WORDS.clear;
    return !(x > left && x < right && high > near && high < far);
  }

  setColours({ ink, ground, raised, glass }) {
    // The card wears the colour of the page's own cards.
    this.cardMaterial.color.copy(raised || ground);
    this.edgeMaterial.color.copy(ink);
    this.tieMaterial.color.copy(ink);
    this.washMaterial.color.copy(ink);
    this.glassMaterial.color.copy(glass);
    this.glassMaterial.userData.rim.uRimColor.value.copy(glass).lerp(new THREE.Color(1, 1, 1), 0.55);
  }

  // ------------------------------------------------------------ labels

  /**
   * A label that follows a point of the close-up. at: [x, y, z] in the piece's units (or in
   * the card's, flat, with `flat`). Returns a handle: set(text), move(x, y, z), show(on).
   */
  label({ text = "", at = [0, 0, 0], kind = "closeup", lift = 0, flat = false }) {
    const handle = { text, local: new THREE.Vector3(...at), anchor: new THREE.Vector3(), kind, lift, flat, shown: true, under: false, label: null };
    handle.set = (next) => {
      handle.text = next;
      if (handle.label && this.labels) this.labels.setText(handle.label, next);
    };
    // A label hangs above its point; `below` hangs it under the point (for the tip of an arrow that points down).
    handle.below = (on) => (handle.under = on);
    handle.move = (x, y, z = 0) => handle.local.set(x, y, z);
    handle.show = (on) => {
      handle.shown = on;
      if (handle.label) handle.label.hidden = !on;
    };
    handle.remove = () => {
      if (handle.label && this.labels) this.labels.remove(handle.label);
      this.handles = this.handles.filter((other) => other !== handle);
    };
    this.handles.push(handle);
    if (this.labels) this.attachOne(handle);
    return handle;
  }

  attachOne(handle) {
    handle.label = this.labels.add({ text: handle.text, anchor: handle.anchor, priority: 990, kind: handle.kind, lift: handle.lift });
    handle.label.boost = 1000; // the close-up's own words are always shown
    handle.label.hidden = !handle.shown;
  }

  /** Put the close-up's labels into a label layer; `detach` forgets them when the layer has been cleared. */
  attach(labels) {
    this.labels = labels;
    for (const handle of this.handles) this.attachOne(handle);
  }

  detach() {
    this.labels = null;
    this.captionRoom = null;
    for (const handle of this.handles) handle.label = null;
  }

  // ------------------------------------------------------------ placing

  /** The card's shape for the caption's height, in the piece's units. */
  layout() {
    const bottom = CARD.low - this.captionHeight / this.unitPx - CARD.foot;
    this.bottom = bottom;
    // The card lies in the plane of the piece's middle and is drawn before it: nothing here is hidden by depth.
    const width = CARD_WIDTH, height = CARD.top - bottom, x = (CARD.left + CARD.right) / 2, y = (CARD.top + bottom) / 2, z = 0;
    this.card.position.set(x, y, z);
    this.card.scale.set(width, height, 1);
    this.edge.geometry.attributes.position.array.set([CARD.left, bottom, z, CARD.right, bottom, z, CARD.right, CARD.top, z, CARD.left, CARD.top, z]);
    this.edge.geometry.attributes.position.needsUpdate = true;
    return { width, height, x, y };
  }

  /** Where the caption's label hangs: the middle of the card's foot, in the card's units. */
  get captionAt() {
    return [(CARD.left + CARD.right) / 2, this.bottom + CARD.foot * 0.5, 0];
  }

  /** The card's width on the screen for a window and its free part, in pixels. */
  static widthFor(stageWidth, free) {
    return Math.max(200, Math.min(free.right - free.left - 2 * MARGIN, Math.max(300, 0.3 * stageWidth), 430));
  }

  /**
   * Place the close-up for this frame: `stage` gives the camera and the window's size, `cell`
   * the point of the scene it is tied to (the top of its cell), `free` the part of the
   * window that no panel covers.
   */
  place(stage, cell, free) {
    const { camera, width, height } = stage;
    camera.updateMatrixWorld();
    const seen = scratchA.copy(cell).applyMatrix4(camera.matrixWorldInverse);
    const depth = Math.max(-seen.z, camera.near * 2);
    const at = stage.project(cell, scratchB);
    const cellPx = { x: at.x, y: at.y };
    const worldPerPx = (2 * depth * Math.tan((camera.fov * Math.PI) / 360)) / height / (camera.zoom || 1);
    let cardPx = Closeup.widthFor(width, free);
    // Where the free part of the window is too low for the card, the card is drawn smaller, down to two thirds.
    const room = free.bottom - free.top - 2 * MARGIN, tall = this.placed ? this.placed.height / this.placed.width : 0;
    if (tall && cardPx * tall > room) cardPx = Math.max(cardPx * 0.66, room / tall);
    this.unitPx = cardPx / CARD_WIDTH;
    // The caption is as wide as the card, less a margin: its lines break to fit, and the card is as tall as they need.
    const caption = this.caption?.label;
    if (caption) {
      const room = Math.round(cardPx - 22);
      if (this.captionRoom !== room || this.captionText !== caption.text) {
        this.captionRoom = room;
        this.captionText = caption.text;
        caption.element.style.width = `${room}px`;
        caption.width = caption.element.offsetWidth;
        caption.height = caption.element.offsetHeight;
      }
      this.captionHeight = caption.height;
    }
    const shape = this.layout();
    const place = cardPlace(cellPx, free, cardPx, shape.height * this.unitPx);
    // The card's middle on the screen, at the depth of the cell, back in the scene.
    const ray = scratchC.set((place.x / width) * 2 - 1, -((place.y / height) * 2 - 1), 0.5).unproject(camera).sub(camera.position).normalize();
    const forward = camera.getWorldDirection(scratchD);
    const middle = scratchE.copy(camera.position).addScaledVector(ray, depth / ray.dot(forward));
    const scale = this.unitPx * worldPerPx;
    this.group.quaternion.copy(camera.quaternion);
    this.group.scale.set(scale, scale, scale * DEPTH);
    // The group's origin is the piece's middle; the card's middle lies at (shape.x, shape.y) from it.
    const right = scratchA.set(1, 0, 0).applyQuaternion(camera.quaternion), up = scratchB.set(0, 1, 0).applyQuaternion(camera.quaternion);
    this.group.position.copy(middle).addScaledVector(right, -shape.x * scale).addScaledVector(up, -shape.y * scale);
    this.group.updateMatrixWorld(true);
    if (this.caption) this.caption.move(...this.captionAt);
    for (const handle of this.handles) {
      handle.anchor.copy(handle.local).applyMatrix4(handle.flat ? this.group.matrixWorld : this.piece.matrixWorld);
      if (handle.label) handle.label.lift = handle.under ? -(handle.label.height + 3) : handle.lift;
    }
    // The tie: from the cell to the two corners of the card's near edge, each band a pixel and a half wide.
    const y = place.side === "bottom" ? this.bottom : CARD.top, z = 0;
    const sight = scratchF.copy(forward);
    const a = scratchC.set(CARD.left, y, z).applyMatrix4(this.group.matrixWorld), b = scratchD.set(CARD.right, y, z).applyMatrix4(this.group.matrixWorld);
    this.wash.geometry.attributes.position.array.set([cell.x, cell.y, cell.z, a.x, a.y, a.z, b.x, b.y, b.z]);
    this.wash.geometry.attributes.position.needsUpdate = true;
    const bands = this.tie.geometry.attributes.position.array, half = 0.75 * worldPerPx;
    [a, b].forEach((corner, k) => {
      // Across the band: at right angles to it and to the line of sight.
      const side = scratchG.copy(corner).sub(cell).cross(sight).normalize().multiplyScalar(half);
      bands.set([cell.x + side.x, cell.y + side.y, cell.z + side.z, corner.x + side.x, corner.y + side.y, corner.z + side.z, corner.x - side.x, corner.y - side.y, corner.z - side.z, cell.x - side.x, cell.y - side.y, cell.z - side.z], k * 12);
    });
    this.tie.geometry.attributes.position.needsUpdate = true;
    this.placed = { ...place, unitPx: this.unitPx, cell: cellPx };
    return this.placed;
  }

  dispose() {
    for (const handle of [...this.handles]) handle.remove();
    this.root.remove(this.group, this.ties);
    for (const object of [this.card, this.edge, this.slab, this.tie, this.wash]) object.geometry.dispose();
    for (const material of [this.cardMaterial, this.edgeMaterial, this.glassMaterial, this.tieMaterial, this.washMaterial]) material.dispose();
  }
}

const scratchA = new THREE.Vector3(), scratchB = new THREE.Vector3(), scratchC = new THREE.Vector3(), scratchD = new THREE.Vector3(), scratchE = new THREE.Vector3(), scratchF = new THREE.Vector3(), scratchG = new THREE.Vector3();
