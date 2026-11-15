// The drawing of a species' own proteins on shelves (schema/SPECIES_PROTEINS.md), for the
// protein atlas lens. The data and where each marker stands come from protein_shelves.js.
//
// The shelves stack, as the atlas's membranes do:
//   the plate   a stretch of membrane. What spans it stands in it; what is outside stands on it.
//   the tray    clear glass below and in front: what is inside the cell.
//   apart       an outline with no glass, further to the front: what has no known side.
// A protein that the atlas draws as a unit is drawn as that unit, small; every other protein
// is a plain marker, for which Cells has no law. A large catalogue stands as families: one
// round marker each, sized by its members. Pressing one opens it: a small set of shelves of
// its own rises from it, round, with every member on it: in its piece of membrane or on it,
// on the glass around it, or set apart beyond the rim.

import * as THREE from "../three.js";
import { soften } from "../core/materials.js";
import { disposeTree } from "../core/stage.js";
import { SHEET, membrane, outline } from "./protein_parts.js";
import { PITCH, layoutShelves, layoutDish, plural } from "./protein_shelves.js";

const HALF = SHEET / 2;
const MARGIN = 6; // from the outermost block to a shelf's edge
const TRAY_DROP = 15; // how far below the membrane the tray lies
const TRAY_THICK = 0.7;
const STEP = 9; // between one shelf's front edge and the next shelf's back edge
const BEAD = 1.02; // a protein marker's radius
const GLASS = -HALF - 1.4; // the glass of an open family, against its piece of membrane
const OPENING = 620, CLOSING = 320; // milliseconds
const VEIL = 0.8; // how much of the shelves the page's own colour covers while a family is open
const RISE = HALF + 20; // how high above the membrane an open family comes to stand, at the least
const WHITE = new THREE.Color(0xffffff), BLACK = new THREE.Color(0x000000);
const ease = (t) => 1 - Math.pow(1 - Math.min(1, Math.max(0, t)), 3);

let cache = null;
function shapes() {
  if (cache) return cache;
  const lathe = (points, segments = 28) => new THREE.LatheGeometry(points.map(([r, y]) => new THREE.Vector2(r, y)), segments);
  cache = {
    bead: new THREE.SphereGeometry(1, 18, 12),
    beadPlain: new THREE.SphereGeometry(1, 10, 7), // for a family of very many
    span: new THREE.CapsuleGeometry(0.86, SHEET + 0.5, 5, 14), // one protein across the membrane
    spanPlain: new THREE.CapsuleGeometry(0.86, SHEET + 0.5, 3, 8),
    stalk: new THREE.CylinderGeometry(0.14, 0.14, 1, 6),
    // A family: a round box with a soft upper edge, one unit across and one high.
    puck: lathe([[0, -0.5], [1, -0.5], [1, 0.28], [0.9, 0.5], [0, 0.5]]),
    ring: new THREE.TorusGeometry(1, 0.02, 8, 72),
    disc: new THREE.CylinderGeometry(1, 1, 1, 72),
  };
  return cache;
}

/** A thin clear slab with rounded corners, lying in the xz plane: a tray. */
function tray(width, depth, radius = 6) {
  const shape = new THREE.Shape();
  const x = -width / 2, y = -depth / 2, r = Math.min(radius, width / 2, depth / 2);
  shape.moveTo(x + r, y);
  shape.lineTo(x + width - r, y);
  shape.quadraticCurveTo(x + width, y, x + width, y + r);
  shape.lineTo(x + width, y + depth - r);
  shape.quadraticCurveTo(x + width, y + depth, x + width - r, y + depth);
  shape.lineTo(x + r, y + depth);
  shape.quadraticCurveTo(x, y + depth, x, y + depth - r);
  shape.lineTo(x, y + r);
  shape.quadraticCurveTo(x, y, x + r, y);
  const slab = new THREE.ExtrudeGeometry(shape, { depth: TRAY_THICK, bevelEnabled: false, curveSegments: 8 });
  slab.rotateX(-Math.PI / 2);
  slab.translate(0, -TRAY_THICK, 0);
  return slab;
}

/**
 * The view from a given direction that shows a box whole within the part of the screen that
 * is free. `free` gives, as shares of the screen, what is covered at each edge.
 */
function fitView(stage, box, { polar, azimuth, free }) {
  const half = Math.tan((stage.camera.fov * Math.PI) / 360), aspect = stage.camera.aspect;
  const away = new THREE.Vector3(Math.sin(polar) * Math.sin(azimuth), Math.cos(polar), Math.sin(polar) * Math.cos(azimuth)); // from the target to the camera
  const right = new THREE.Vector3(Math.cos(azimuth), 0, -Math.sin(azimuth));
  const up = new THREE.Vector3().crossVectors(away, right);
  const corners = [];
  for (const x of [box.minX, box.maxX]) for (const y of [box.minY, box.maxY]) for (const z of [box.minZ, box.maxZ]) corners.push(new THREE.Vector3(x, y, z));
  const target = new THREE.Vector3((box.minX + box.maxX) / 2, (box.minY + box.maxY) / 2, (box.minZ + box.maxZ) / 2);
  // The free part of the screen, in the camera's own measure (-1 to 1 each way).
  const left = -1 + 2 * free.left, rightEdge = 1 - 2 * free.right, bottom = -1 + 2 * free.bottom, top = 1 - 2 * free.top;
  let distance = Math.max(box.maxX - box.minX, box.maxZ - box.minZ) / half;
  const offset = new THREE.Vector3();
  for (let pass = 0; pass < 8; pass++) {
    let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
    for (const corner of corners) {
      offset.subVectors(corner, target);
      const depth = Math.max(1e-3, distance - offset.dot(away));
      const x = offset.dot(right) / (depth * half * aspect), y = offset.dot(up) / (depth * half);
      minX = Math.min(minX, x);
      maxX = Math.max(maxX, x);
      minY = Math.min(minY, y);
      maxY = Math.max(maxY, y);
    }
    // Further away or nearer until it fills the free part, then moved so that it is in its middle.
    distance *= Math.max((maxX - minX) / (rightEdge - left), (maxY - minY) / (top - bottom));
    target.addScaledVector(right, ((minX + maxX) / 2 - (left + rightEdge) / 2) * distance * half * aspect);
    target.addScaledVector(up, ((minY + maxY) / 2 - (bottom + top) / 2) * distance * half);
  }
  return { target, distance, azimuth, polar };
}

/**
 * What the page's own furniture covers of the screen, as shares of it: the bar above, the
 * note below, and the card, which stands at the left on a wide window and above on a narrow one.
 */
export function freeOf(stage, { panel = false } = {}) {
  const { width, height } = stage;
  // The panel of a chosen part: the stage shifts its picture by half of what the panel covers, so each side gives that up.
  const beside = panel ? (stage.insets?.right || 0) / 2 : 0, below = panel ? (stage.insets?.bottom || 0) / 2 : 0;
  // On a narrow window the card stands above the picture, and gives way to the panel when one is open.
  if (width < 760) return below ? { left: 22 / width, right: 22 / width, top: (64 + below) / height, bottom: (12 + below) / height } : { left: 22 / width, right: 22 / width, top: Math.min(0.42, 292 / height), bottom: Math.min(0.24, 124 / height) };
  return { left: Math.min(0.34, 304 / width) + beside / width, right: (20 + beside) / width, top: 78 / height, bottom: 100 / height };
}

// How deep a stack of shelves may be for its width, to fill the free part of a screen seen from the front and above.
const SHAPES = [0.65, 0.8, 1.25, 2.4];

/** The shape of stack that suits the screen as it is: one of a few, so that a layout is made once for each. */
export function shapeFor(stage) {
  const free = freeOf(stage);
  const ratio = ((1 - free.top - free.bottom) * stage.height) / Math.max(1, (1 - free.left - free.right) * stage.width);
  const wanted = ratio / 0.75 - 0.1;
  return SHAPES.reduce((best, shape) => (Math.abs(shape - wanted) < Math.abs(best - wanted) ? shape : best));
}

function circle(radius, steps = 96) {
  const points = Array.from({ length: steps + 1 }, (_, index) => new THREE.Vector3(Math.cos((index / steps) * Math.PI * 2) * radius, 0, Math.sin((index / steps) * Math.PI * 2) * radius));
  return new THREE.BufferGeometry().setFromPoints(points);
}

/** Many copies of one shape as one mesh; each place gives its position and scale, and learns its index. */
function instanced(geometry, material, places, at = (place) => place.position) {
  const scratch = new THREE.Object3D();
  const mesh = new THREE.InstancedMesh(geometry, material, places.length);
  places.forEach((place, index) => {
    scratch.position.copy(at(place));
    scratch.scale.fromArray(place.scale || [1, 1, 1]);
    scratch.updateMatrix();
    mesh.setMatrixAt(index, scratch.matrix);
    mesh.setColorAt(index, WHITE);
    place.mesh = mesh;
    place.index = index;
  });
  mesh.instanceMatrix.needsUpdate = true;
  mesh.computeBoundingSphere();
  return mesh;
}

export class ShelvesView {
  /**
   * lens     the protein atlas lens: its stage, its tones and how it builds a unit's form
   * shelves  one species' proteins (protein_shelves.js)
   * shape    how deep the stack may be for its width: about 1 on a wide screen, more on a tall one
   */
  constructor(lens, shelves, { shape = 1.15 } = {}) {
    this.lens = lens;
    this.stage = lens.stage;
    this.shelves = shelves;
    this.shape = shape;
    this.group = new THREE.Group();
    this.nodes = new Map(); // key -> { item, position, radius, top, ringAt, area, tone, mesh, index, form, pip, label }
    this.meshes = [];
    this.areas = [];
    this.districts = [];
    this.clusters = [];
    this.protos = new Map(); // a unit's form, made once and copied
    this.selected = null;
    this.hovered = null;
    this.isolate = null; // a side
    this.basis = null; // how a side is known
    this.mark = null; // { name, value }
    this.units = false; // only what Cells has a law for
    this.opened = null; // the family, part or gathering that is open
    this.wanted = null; // the one being fetched
    this.status = null; // what the view is doing, or why it could not
    this.failed = false; // whether that status says something could not be done
    this.dish = null;
    this.leaving = null; // the dish that is closing
    this.colours = {};
    this.build();
  }

  // ------------------------------------------------------------ building

  /** The scene's part for the first of an item's units that the scene has, or null. */
  unitOf(item) {
    for (const id of item.units || []) {
      const entity = this.lens.model.get(this.shelves.units.get(id));
      if (entity?.form) return entity;
    }
    return null;
  }

  /** A unit's form, copied from one made once: { entity, group, meshes, reach }. */
  formFor(entity) {
    let proto = this.protos.get(entity.id);
    if (!proto) this.protos.set(entity.id, (proto = this.lens.makeUnit(entity)));
    const group = proto.group.clone(true);
    const meshes = [];
    group.traverse((object) => object.isMesh && meshes.push(object));
    return { entity, group, meshes, reach: proto.reach };
  }

  build() {
    const { shelves } = this;
    const G = shapes();
    const layout = layoutShelves(shelves, { shape: this.shape, margin: MARGIN, step: STEP });
    const families = shelves.kind === "families";
    // The stack: each shelf lies lower than the one before it and further to the front.
    const present = ["plate", "tray", "apart"].map((id) => layout[id]).filter((area) => area.blocks.length);
    const LEVEL = { plate: 0, tray: -TRAY_DROP, apart: -TRAY_DROP - 7 };
    // The membrane and the glass are one width, so they read as shelves of one stack.
    const shelf = Math.max(0, ...present.filter((area) => area.id !== "apart").map((area) => area.width));
    let front = null;
    for (const area of present) {
      area.width = (area.id === "apart" ? area.width : Math.max(area.width, shelf)) + 2 * MARGIN;
      area.depth += 2 * MARGIN;
      area.centre = new THREE.Vector3(0, LEVEL[area.id], front === null ? 0 : front + STEP + area.depth / 2);
      front = area.centre.z + area.depth / 2;
      // The face of the shelf on which, or in which, its markers stand.
      area.top = area.id === "plate" ? HALF : area.centre.y;
    }
    this.areas = present;

    this.lineMaterial = new THREE.LineBasicMaterial({ transparent: true, opacity: 0.4, depthWrite: false });
    this.dashes = new THREE.LineDashedMaterial({ transparent: true, opacity: 0.85, dashSize: 1.1, gapSize: 0.8 });
    this.trayMaterial = new THREE.MeshStandardMaterial({ roughness: 0.35, metalness: 0, transparent: true, opacity: 0.3, depthWrite: false, side: THREE.DoubleSide });
    // Under an open family, a sheet of the page's own colour over the shelves: they stand back,
    // and a click beside the family reaches nothing on them.
    this.veilMaterial = new THREE.MeshBasicMaterial({ transparent: true, opacity: 0, depthWrite: false });
    this.sheets = [];
    for (const area of present) {
      if (area.id === "plate") {
        const sheet = membrane(area.width, area.depth, 7);
        sheet.group.position.copy(area.centre);
        this.sheets.push(sheet);
        this.group.add(sheet.group);
      } else if (area.id === "tray") {
        const glass = new THREE.Mesh(tray(area.width, area.depth, 7), this.trayMaterial);
        glass.position.copy(area.centre);
        glass.renderOrder = 2;
        glass.userData.unpickable = true;
        const rim = new THREE.LineLoop(outline(area.width, area.depth, 7), this.lineMaterial);
        rim.position.copy(area.centre);
        rim.userData.unpickable = true;
        this.group.add(glass, rim);
      } else {
        // No glass under what is set apart: an outline only, so it reads as outside the shelves.
        const edge = new THREE.LineLoop(outline(area.width, area.depth, 7), this.dashes);
        edge.computeLineDistances();
        edge.position.copy(area.centre);
        edge.userData.unpickable = true;
        this.group.add(edge);
      }
    }

    // What each marker looks like, by the shelf it stands on and its side.
    const solid = new THREE.MeshStandardMaterial({ roughness: 0.5, metalness: 0 });
    soften(solid, { rim: 0.3 });
    const ghost = new THREE.MeshStandardMaterial({ roughness: 0.6, metalness: 0, transparent: true, opacity: 0.55, depthWrite: false });
    this.materials = { solid, ghost, stalk: new THREE.MeshStandardMaterial({ roughness: 0.7, metalness: 0 }) };
    const sets = new Map();
    const set = (name, geometry, material) => {
      if (!sets.has(name)) sets.set(name, { geometry, material, places: [] });
      return sets.get(name).places;
    };
    this.forms = [];
    for (const area of present) {
      for (const block of area.blocks) {
        const centre = new THREE.Vector3(area.centre.x + block.x, area.top, area.centre.z + block.z);
        // The district's outline lies on its shelf, and its name just in front of it.
        const edge = new THREE.LineLoop(outline(block.width - 1.2, block.depth - 1.2, 3), this.lineMaterial);
        edge.position.set(centre.x, area.top + 0.08, centre.z);
        edge.userData.unpickable = true;
        edge.renderOrder = 3;
        this.group.add(edge);
        this.districts.push({ id: `${area.id}:${block.district}`, area: area.id, district: block.district, label: block.label, path: shelves.districtPath(block.places[0].item), count: block.count, anchor: new THREE.Vector3(centre.x, area.top, centre.z + block.depth / 2 + 1.6), places: block.places });
        for (const place of block.places) {
          const item = place.item;
          const x = centre.x + place.dx, z = centre.z + place.dz;
          const unknown = item.side === "not known";
          const node = { item, area: area.id, radius: families ? place.radius : BEAD, tone: item.holds ? "more" : item.units.length ? "unit" : "plain" };
          const entity = this.unitOf(item);
          if (families) {
            // A family stands as a round box: through the membrane, on a stalk above it, or on the glass.
            const high = item.side === "in" ? SHEET + 1.5 : 1.7;
            const y = item.side === "in" ? 0 : item.side === "outside" ? HALF + 2.6 + high / 2 : area.top + high / 2;
            node.position = new THREE.Vector3(x, y, z);
            node.top = y + high / 2;
            node.scale = [place.radius, high, place.radius];
            set(unknown ? "puck-ghost" : "puck", G.puck, unknown ? ghost : solid).push(node);
            if (item.side === "outside") set("stalk", G.stalk, this.materials.stalk).push({ stalk: true, position: new THREE.Vector3(x, HALF + 1.3, z), scale: [2.2, 2.6, 2.2] });
            if (entity && !item.holds) {
              // A family that holds a machine Cells has a law for carries that unit's form, small.
              const form = this.formFor(entity);
              const fit = Math.min(0.62, (place.radius * 0.92) / form.reach.radius);
              form.group.scale.setScalar(fit);
              form.group.position.set(x, item.side === "in" ? 0.35 : node.top - form.reach.bottom * fit + 0.1, z);
              node.top = Math.max(node.top, form.group.position.y + form.reach.top * fit);
              node.form = form;
            } else if (item.holds && item.units.length) {
              // A gathering that holds such families among others carries a small sign of it.
              node.pip = { pip: true, position: new THREE.Vector3(x, node.top + 0.45, z), scale: [0.62, 0.62, 0.62] };
              set("pip", G.bead, solid).push(node.pip);
              node.top += 1.1;
            }
          } else if (entity) {
            // A protein that the atlas draws as a unit is drawn as that unit, small.
            const form = this.formFor(entity);
            const fit = Math.min(0.34, (PITCH * 0.47) / form.reach.radius);
            const base = item.side === "in" || item.side === "outside" ? HALF : area.top;
            form.group.scale.setScalar(fit);
            // So small, a form that spans the membrane would lie hidden within it: it stands sunk in it, its top out, as the plain markers do.
            form.group.position.set(x, item.side === "in" ? HALF + 1.5 - form.reach.top * fit : base - form.reach.bottom * fit, z);
            node.position = form.group.position.clone();
            node.top = form.group.position.y + form.reach.top * fit;
            node.radius = form.reach.radius * fit;
            node.form = form;
            // A clear form is hard to see when small: each stands on a base of the units' colour.
            node.foot = { foot: true, item, position: new THREE.Vector3(x, base + 0.14, z), scale: [PITCH * 0.44, 0.28, PITCH * 0.44] };
            set("foot", G.puck, solid).push(node.foot);
          } else if (item.side === "in") {
            node.position = new THREE.Vector3(x, 0.2, z);
            node.top = HALF + 1.3;
            set("span", G.span, solid).push(node);
          } else if (item.side === "outside") {
            node.position = new THREE.Vector3(x, HALF + 2.3, z);
            node.top = HALF + 2.3 + BEAD;
            node.scale = [BEAD, BEAD, BEAD];
            set("bead", G.bead, solid).push(node);
            set("stalk", G.stalk, this.materials.stalk).push({ stalk: true, position: new THREE.Vector3(x, HALF + 0.75, z), scale: [1, 1.5, 1] });
          } else {
            node.position = new THREE.Vector3(x, area.top + BEAD, z);
            node.top = area.top + 2 * BEAD;
            node.scale = [BEAD, BEAD, BEAD];
            set(unknown ? "bead-ghost" : "bead", G.bead, unknown ? ghost : solid).push(node);
          }
          if (node.form) {
            node.form.group.userData.pick = item.key; // a click on the form picks its protein or its family
            this.forms.push(node.form);
            this.group.add(node.form.group);
          }
          node.ringAt = new THREE.Vector3(x, item.side === "in" || item.side === "outside" ? HALF + 0.2 : area.top + 0.15, z);
          this.nodes.set(item.key, node);
        }
      }
    }
    for (const [name, { geometry, material, places }] of sets) {
      const mesh = instanced(geometry, material, places);
      mesh.renderOrder = name.endsWith("ghost") ? 5 : 4;
      if (name === "stalk" || name === "pip") mesh.userData.unpickable = true;
      else mesh.userData.pick = (hit) => places[hit.instanceId]?.item.key ?? null;
      this.group.add(mesh);
      this.meshes.push(mesh);
    }
    for (const node of this.nodes.values()) if (node.foot) node.mesh = null; // drawn as a form: the base is not its marker

    // A gathering of smaller families is ringed with dashes, so it reads as many and not one.
    for (const node of this.nodes.values()) {
      if (!node.item.holds) continue;
      const loop = new THREE.LineLoop(circle(node.radius + 0.5, 48), this.dashes);
      loop.computeLineDistances();
      loop.position.set(node.position.x, node.position.y + node.scale[1] / 2 + 0.05, node.position.z);
      loop.userData.unpickable = true;
      this.group.add(loop);
    }
    // The members of one assembly, where the data names it, share a label.
    if (!families) {
      const groups = new Map();
      for (const node of this.nodes.values()) {
        const name = node.item.marks?.complex;
        if (!name) continue;
        const id = `${node.area}:${node.item.group}:${name}`;
        if (!groups.has(id)) groups.set(id, { name, nodes: [] });
        groups.get(id).nodes.push(node);
      }
      for (const cluster of groups.values()) {
        if (cluster.nodes.length < 3) continue;
        const centre = cluster.nodes.reduce((sum, node) => sum.add(node.position), new THREE.Vector3()).multiplyScalar(1 / cluster.nodes.length);
        centre.y = Math.max(...cluster.nodes.map((node) => node.top));
        this.clusters.push({ label: `${cluster.name.charAt(0).toUpperCase()}${cluster.name.slice(1)} · ${cluster.nodes.length}`, anchor: centre });
      }
    }

    // One ring marks what is in focus, a lighter one what is under the pointer.
    this.ring = new THREE.Mesh(G.ring, new THREE.MeshBasicMaterial());
    this.hoverRing = new THREE.Mesh(G.ring, new THREE.MeshBasicMaterial({ transparent: true, opacity: 0.6 }));
    for (const mark of [this.ring, this.hoverRing]) {
      mark.rotation.x = Math.PI / 2;
      mark.visible = false;
      mark.renderOrder = 8;
      mark.userData.unpickable = true;
      this.group.add(mark);
    }
    this.fill = new THREE.DirectionalLight(0xffffff, 0.6);
    this.fill.position.set(-80, -30, 60);
    this.group.add(this.fill);

    const first = present[0], last = present[present.length - 1];
    const widest = Math.max(...present.map((area) => area.width));
    this.bounds = { minX: -widest / 2, maxX: widest / 2, minZ: first.centre.z - first.depth / 2, maxZ: last.centre.z + last.depth / 2, minY: Math.min(...present.map((area) => area.centre.y)) - 2, maxY: HALF + 6 };
    this.veil = new THREE.Mesh(G.disc, this.veilMaterial);
    const far = 3 * Math.max(widest, this.bounds.maxZ - this.bounds.minZ);
    this.veil.scale.set(far, 0.05, far);
    this.veil.position.set(0, RISE - 5.2, (this.bounds.minZ + this.bounds.maxZ) / 2); // above what stands on the shelves, below an open family
    this.veil.renderOrder = 5;
    this.veil.visible = false;
    this.veil.userData.blocker = true;
    this.group.add(this.veil);
    // The names of the sides lie at the back of the shelves they belong to.
    const words = shelves.sideWords();
    this.sides = [];
    for (const area of present) {
      const left = -area.width / 2 + 3, back = area.centre.z - area.depth / 2;
      if (area.id === "plate") {
        this.sides.push({ text: words.outside.short, anchor: new THREE.Vector3(left, HALF + 9, back + 2) });
        // The membrane carries the shelf's own name, as the file gives it: it may stand for several membranes.
        this.sides.push({ text: shelves.shelf.label, anchor: new THREE.Vector3(area.width * 0.2, HALF, back + 1), shelf: true });
      } else if (area.id === "tray") this.sides.push({ text: words.inside.short, anchor: new THREE.Vector3(left, area.centre.y + 5, back + 1) });
      else this.sides.push({ text: "Side not known: set apart", anchor: new THREE.Vector3(left, area.centre.y + 5, back + 1) });
    }
  }

  // ------------------------------------------------------------ what the lens asks

  has(key) {
    return Boolean(this.shelves.get(key));
  }

  /** The markers at rest, and the members of what is open. */
  entities() {
    const items = [...this.shelves.markers];
    if (this.opened) items.push(...(this.shelves.membersOf(this.opened) || []));
    return items.map((item) => this.shelves.listed(item));
  }

  /**
   * The list: the members of what is open, then every marker under its shelf and district.
   * A long section shows its first rows until something is typed; the smaller families,
   * which stand gathered, are found by name only.
   */
  sections() {
    const shelves = this.shelves, words = shelves.sideWords();
    const out = [];
    if (this.opened) {
      const members = shelves.membersOf(this.opened) || [];
      out.push({ label: `Open: ${this.opened.label} · ${plural(members.length, "protein")}`, entities: members.map((item) => shelves.listed(item)), limit: 300 });
    }
    for (const district of this.districts) {
      const side = district.area === "plate" ? `${words.in.short} or ${words.outside.short.toLowerCase()}` : district.area === "tray" ? words.inside.short : "Side not known";
      out.push({ label: `${district.path} · ${side}`, entities: district.places.map((place) => shelves.listed(place.item)), limit: 200 });
    }
    if (shelves.kind === "families") {
      const small = [...shelves.families, ...shelves.parts].filter((item) => item.within);
      out.push({ label: "Smaller families and groups", entities: small.map((item) => shelves.listed(item)), searchOnly: true, limit: 200 });
    }
    return out;
  }

  describe(key) {
    return this.shelves.describe(key);
  }

  /** The node a key is drawn at: its own marker, a member's place when its family is open, or the marker that holds it. */
  nodeOf(key) {
    if (this.dish?.nodes.has(key)) return this.dish.nodes.get(key);
    if (this.nodes.has(key)) return this.nodes.get(key);
    const item = this.shelves.get(key);
    const outer = item?.within || item?.under?.within || item?.under;
    return outer ? this.nodes.get(outer.key) || null : null;
  }

  lit(item) {
    // A family is on a side if any of its members is: the legend counts proteins.
    if (this.isolate && (item.type === "p" ? item.side !== this.isolate : !(item.sides?.[this.isolate] > 0))) return false;
    if (this.units && !item.units.length) return false;
    if (item.type === "p") {
      if (this.basis && item.basis !== this.basis) return false;
      if (this.mark && String(item.marks?.[this.mark.name] ?? false) !== this.mark.value) return false;
    }
    return true;
  }

  // ------------------------------------------------------------ opening a family

  /** What opens when a key is chosen: the family, the part or the gathering that holds it; null for a protein at rest. */
  opener(key) {
    const item = this.shelves.get(key);
    if (!item || this.shelves.kind !== "families") return null;
    if (item.type === "p") return item.under ? item.under.within || item.under : null;
    return item.within || item;
  }

  /**
   * Open a family, a part or a gathering: its members' files are fetched if need be, and a
   * small set of shelves rises from its marker with every member on it. Returns, or settles
   * to, whether it is open: true, or false if it could not be.
   */
  open(key) {
    const item = this.opener(key);
    if (!item) return false;
    if (this.opened === item) return true;
    if (this.wanted === item && this.opening) return this.opening; // already on its way
    this.wanted = item;
    this.failed = false;
    const opening = this.bring(item).finally(() => {
      if (this.opening === opening) this.opening = null;
    });
    this.opening = opening;
    return opening;
  }

  /** Fetch what a family needs and build its shelves; see open(). */
  async bring(item) {
    const shelves = this.shelves;
    if (!shelves.membersOf(item)) {
      this.status = `Fetching the proteins of ${item.label}…`;
      this.lens.onChrome?.();
      try {
        await this.lens.loadMembers(shelves, shelves.filesOf(item));
      } catch (error) {
        if (this.wanted === item) {
          this.wanted = null;
          this.status = `The proteins of ${item.label} could not be loaded (${error.message}).`;
          this.failed = true;
          this.lens.onChrome?.();
        }
        return false;
      }
      if (this.wanted !== item) return false; // another one was asked for meanwhile
    }
    let members;
    try {
      members = shelves.membersOf(item);
    } catch (error) {
      this.wanted = null;
      this.status = `The proteins of ${item.label} could not be shown: ${error.message}.`;
      this.failed = true;
      this.lens.onChrome?.();
      return false;
    }
    this.status = null;
    this.wanted = null;
    this.close({ quiet: true });
    this.opened = item;
    this.buildDish(item, members);
    this.paint();
    this.lens.onOpen?.();
    return true;
  }

  buildDish(item, members) {
    const G = shapes();
    const node = this.nodeOf(item.key);
    const layout = layoutDish(members, PITCH, (member) => Boolean(this.unitOf(member)));
    const plain = members.length > 900; // very many: simpler shapes
    const group = new THREE.Group();
    const owned = []; // what this dish alone uses, to free when it closes
    // What is see-through is drawn in this order: the veil over the shelves, the glass, the piece of membrane, then the members.
    let sheet = null;
    if (layout.plate) {
      sheet = membrane(2 * layout.plate, 2 * layout.plate, layout.plate);
      sheet.group.traverse((object) => (object.renderOrder = 7));
      group.add(sheet.group);
    }
    if (layout.tray) {
      const glass = new THREE.Mesh(G.disc, this.trayMaterial);
      glass.scale.set(layout.tray, TRAY_THICK, layout.tray);
      glass.position.y = GLASS - TRAY_THICK / 2;
      glass.renderOrder = 6;
      glass.userData.unpickable = true;
      group.add(glass);
    }
    if (layout.reach > Math.max(layout.plate, layout.tray) + 0.01) {
      const edge = new THREE.LineLoop(circle(layout.reach + 0.6), this.dashes);
      edge.computeLineDistances();
      edge.position.y = GLASS;
      edge.userData.unpickable = true;
      group.add(edge);
      owned.push(edge.geometry);
    }
    const nodes = new Map();
    const sets = new Map();
    const set = (name, geometry, material) => {
      if (!sets.has(name)) sets.set(name, { geometry, material, places: [] });
      return sets.get(name).places;
    };
    const forms = [];
    // In a gathering, neighbouring families alternate in shade, so each reads as one.
    let shade = 0, last = null;
    for (const place of layout.places) {
      const member = place.item;
      if (member.under !== last) {
        shade = 1 - shade;
        last = member.under;
      }
      const entry = { item: member, local: new THREE.Vector3(place.dx, 0, place.dz), radius: BEAD, tone: member.units.length ? "unit" : "plain", shade: item.holds ? shade : 0 };
      const entity = this.unitOf(member);
      const onGlass = place.zone !== "plate";
      if (entity) {
        // A member that the atlas draws as a unit is drawn as that unit.
        const form = this.formFor(entity);
        const fit = Math.min(0.62, (PITCH * 0.94) / form.reach.radius);
        form.group.scale.setScalar(fit);
        entry.local.y = member.side === "in" ? 0.2 : (onGlass ? GLASS : HALF) - form.reach.bottom * fit;
        form.group.position.copy(entry.local);
        form.group.userData.pick = member.key;
        for (const mesh of form.meshes) mesh.renderOrder = 8;
        entry.top = entry.local.y + form.reach.top * fit;
        entry.radius = form.reach.radius * fit;
        entry.form = form;
        forms.push(form);
        group.add(form.group);
        // A clear form is hard to see when small: each stands on a base of the units' colour.
        entry.foot = { foot: true, item: member, local: new THREE.Vector3(place.dx, (onGlass ? GLASS : HALF) + 0.14, place.dz), scale: [PITCH * 0.86, 0.28, PITCH * 0.86] };
        set("foot", G.puck, this.materials.solid).push(entry.foot);
      } else if (member.side === "in") {
        entry.local.y = 0.2;
        entry.top = HALF + 1.3;
        set("span", plain ? G.spanPlain : G.span, this.materials.solid).push(entry);
      } else if (member.side === "outside") {
        entry.local.y = HALF + 2.3;
        entry.top = HALF + 2.3 + BEAD;
        entry.scale = [BEAD, BEAD, BEAD];
        set("bead", plain ? G.beadPlain : G.bead, this.materials.solid).push(entry);
        set("stalk", G.stalk, this.materials.stalk).push({ stalk: true, local: new THREE.Vector3(place.dx, HALF + 0.75, place.dz), scale: [1, 1.5, 1] });
      } else {
        // Inside the cell: on the glass. With no known side: beyond the rim, on nothing.
        entry.local.y = GLASS + BEAD;
        entry.top = GLASS + 2 * BEAD;
        entry.scale = [BEAD, BEAD, BEAD];
        const unknown = member.side === "not known";
        set(unknown ? "bead-ghost" : "bead", plain ? G.beadPlain : G.bead, unknown ? this.materials.ghost : this.materials.solid).push(entry);
      }
      entry.ringY = member.side === "in" || member.side === "outside" ? HALF + 0.2 : GLASS + 0.15;
      entry.zone = place.zone;
      nodes.set(member.key, entry);
    }
    const meshes = [];
    for (const [name, { geometry, material, places }] of sets) {
      const mesh = instanced(geometry, material, places, (place) => place.local);
      mesh.renderOrder = 8;
      if (name === "stalk") mesh.userData.unpickable = true;
      else mesh.userData.pick = (hit) => places[hit.instanceId]?.item.key ?? null;
      group.add(mesh);
      meshes.push(mesh);
    }
    for (const entry of nodes.values()) if (entry.foot) entry.mesh = null; // drawn as a form: the base is not its marker
    // It rises from its marker to above the shelves, growing as it goes; a thread keeps it tied to its marker.
    const from = node ? new THREE.Vector3(node.position.x, node.top, node.position.z) : new THREE.Vector3();
    const to = new THREE.Vector3(from.x, RISE + layout.reach * 0.22, from.z);
    let high = HALF + 4;
    for (const entry of nodes.values()) {
      high = Math.max(high, entry.top + 1);
      entry.position = to.clone().add(entry.local);
      entry.ringAt = new THREE.Vector3(entry.position.x, to.y + entry.ringY, entry.position.z);
      entry.top = to.y + entry.top;
    }
    const thread = new THREE.Line(new THREE.BufferGeometry().setFromPoints([from, from.clone()]), this.lineMaterial);
    thread.userData.unpickable = true;
    owned.push(thread.geometry);
    this.group.add(group, thread);
    this.dish = { item, group, thread, nodes, meshes, forms, from, to, reach: layout.reach, high, sheet, owned, count: members.length, grown: 0 };
    this.applyPalette(this.stage.palette);
    const instant = this.stage.rig.instant || this.stage.reducedMotion;
    this.dish.tween = instant ? null : { elapsed: 0, duration: OPENING };
    this.settleDish(this.dish, instant ? 1 : 0);
    // The camera goes to it with the next frame, when the panel that opens with it has its place.
    this.framing = { of: "dish", view: null, key: null };
    this.stage.invalidate();
  }

  /** Place a dish along its way: 0 at its marker, small; 1 above the shelves, full size. */
  settleDish(dish, t) {
    const k = ease(t);
    dish.grown = k;
    this.veil.visible = true;
    this.veilMaterial.opacity = VEIL * k;
    dish.group.position.lerpVectors(dish.from, dish.to, k);
    dish.group.scale.setScalar(0.03 + 0.97 * k);
    dish.group.updateMatrixWorld(true);
    const ends = dish.thread.geometry.attributes.position;
    ends.setXYZ(1, dish.group.position.x, dish.group.position.y + (GLASS - TRAY_THICK) * (0.03 + 0.97 * k), dish.group.position.z);
    ends.needsUpdate = true;
  }

  /** Close what is open. It goes back into its marker; `quiet` when another one opens in its place. */
  close({ quiet = false } = {}) {
    if (!quiet) {
      this.wanted = this.status = null;
      this.failed = false;
    }
    const dish = this.dish;
    if (!dish) return;
    this.dish = null;
    this.opened = null;
    if (this.selected && !this.nodeOf(this.selected)) this.selected = null;
    this.hovered = null;
    const instant = this.stage.rig.instant || this.stage.reducedMotion;
    if (this.leaving) this.drop(this.leaving);
    if (instant) this.drop(dish);
    else {
      dish.tween = { elapsed: 0, duration: CLOSING, from: dish.grown };
      for (const mesh of dish.meshes) mesh.userData.unpickable = true; // what is leaving is not picked
      for (const form of dish.forms) form.group.userData.unpickable = true;
      this.leaving = dish;
    }
    this.paint();
    if (!quiet) {
      this.lens.onOpen?.();
      this.stage.rig.flyTo(this.lens.homeView(), 800);
    }
    this.stage.invalidate();
  }

  /** Take a dish out of the scene and free what it alone used. */
  drop(dish) {
    this.group.remove(dish.group, dish.thread);
    for (const mesh of dish.meshes) mesh.dispose();
    for (const geometry of dish.owned) geometry.dispose();
    if (dish.sheet) {
      dish.sheet.group.traverse((object) => object.geometry?.dispose());
      dish.sheet.body.dispose();
      dish.sheet.faces.dispose();
    }
    if (this.leaving === dish) this.leaving = null;
    if (!this.dish && !this.leaving) {
      this.veil.visible = false;
      this.veilMaterial.opacity = 0;
    }
  }

  update(dt) {
    let moving = false;
    // A family just opened, or the window or the panel changed: the picture is framed again,
    // unless the camera was moved by hand since it was last framed.
    const framing = this.framing;
    if (framing && framing.key !== this.frameKey()) {
      if (framing.view === null) this.stage.rig.flyTo(this.frame(framing.of), 900);
      else if (this.rigAt(framing.view)) this.stage.rig.flyTo(this.frame(framing.of), 420);
      else framing.key = this.frameKey();
      moving = true;
    }
    const dish = this.dish;
    if (dish?.tween) {
      dish.tween.elapsed += dt;
      const t = dish.tween.elapsed / dish.tween.duration;
      this.settleDish(dish, t);
      if (t >= 1) dish.tween = null;
      moving = true;
    }
    const leaving = this.leaving;
    if (leaving) {
      leaving.tween.elapsed += dt;
      const t = leaving.tween.elapsed / leaving.tween.duration;
      // Back along the way it came, from wherever it had got to.
      const k = leaving.tween.from * (1 - Math.min(1, t)) ** 2;
      if (!dish) this.veilMaterial.opacity = VEIL * k; // the shelves come back as it goes, unless another one is open
      leaving.group.position.lerpVectors(leaving.from, leaving.to, k);
      leaving.group.scale.setScalar(0.03 + 0.97 * k);
      const ends = leaving.thread.geometry.attributes.position;
      ends.setXYZ(1, leaving.group.position.x, leaving.group.position.y, leaving.group.position.z);
      ends.needsUpdate = true;
      if (t >= 1) this.drop(leaving);
      moving = true;
    }
    if (moving) this.stage.invalidate();
    return moving;
  }

  // ------------------------------------------------------------ state

  /** Back to rest: nothing chosen, nothing filtered, nothing open. */
  reset() {
    this.selected = this.hovered = null;
    this.isolate = this.basis = this.mark = null;
    this.units = false;
    this.status = this.wanted = null;
    this.failed = false;
    const dishes = [this.dish, this.leaving].filter(Boolean);
    this.dish = this.leaving = this.opened = null;
    for (const dish of dishes) this.drop(dish);
    this.paint();
  }

  /**
   * What is in focus. Choosing a family, a part or a gathering opens it; so does choosing a
   * smaller family that stands gathered, or a protein whose family is not open.
   */
  setSelection(key) {
    this.selected = key && this.shelves.get(key) ? key : null;
    const opens = this.selected ? this.opener(this.selected) : null;
    if (opens && opens !== this.opened) this.open(opens.key);
    this.paint();
  }

  setHover(key) {
    const next = key && this.shelves.get(key) ? key : null;
    if (next === this.hovered) return;
    this.hovered = next;
    this.paint();
  }

  /** The words of the two labels that follow the pointer and the selection. */
  hotText(key) {
    const item = this.shelves.get(key);
    if (!item) return null;
    if (item.type !== "p") return `${item.label} · ${plural(item.count, "protein")}`;
    if (item.gene && item.gene !== item.label) return `${item.gene} · ${item.label}`;
    return item.under ? `${item.label} · ${item.id}` : item.label;
  }

  buildLabels(labels) {
    this.labelLayer = labels;
    for (const district of this.districts) {
      // With many districts on a shelf, the larger ones are named first where names would collide.
      district.tag = labels.add({ text: district.label, anchor: district.anchor, priority: 500 + Math.min(190, Math.sqrt(district.count) * 6), kind: "layer label-district label-shelf", lift: -8 });
    }
    this.notes = this.sides.map((side) => labels.add({ text: side.text, anchor: side.anchor, priority: side.shelf ? 900 : 700, kind: "note", lift: 0 }));
    for (const node of this.nodes.values()) node.label = null;
    if (this.shelves.kind === "families") {
      // The largest families are named where they stand; the rest are named under the pointer.
      const named = [...this.nodes.values()].sort((a, b) => b.item.count - a.item.count).slice(0, 64);
      for (const node of named) {
        const held = node.item.units.length > 0;
        node.label = labels.add({ id: node.item.key, text: node.item.label, anchor: new THREE.Vector3(node.position.x, node.top + 0.4, node.position.z), priority: 20 + Math.log2(node.item.count + 1) + (held ? 6 : 0), kind: "part label-unit", lift: 6, swatch: held ? "map-assigned" : null });
      }
      // Every family that holds a machine Cells has a law for is named too.
      for (const node of this.nodes.values()) {
        if (node.label || !node.form) continue;
        node.label = labels.add({ id: node.item.key, text: node.item.label, anchor: new THREE.Vector3(node.position.x, node.top + 0.4, node.position.z), priority: 30, kind: "part label-unit", lift: 6, swatch: "map-assigned" });
      }
    } else {
      for (const cluster of this.clusters) labels.add({ text: cluster.label, anchor: cluster.anchor, priority: 60, kind: "part label-unit", lift: 8 });
    }
    const hot = () => labels.add({ text: "", anchor: new THREE.Vector3(), priority: 5000, kind: "part label-unit label-hot", lift: 8 });
    this.hot = { selected: hot(), hovered: hot() };
    this.hot.selected.hidden = this.hot.hovered.hidden = true;
    this.dishLabel = labels.add({ text: "", anchor: new THREE.Vector3(), priority: 4000, kind: "layer label-district label-shelf", lift: -10 });
    this.dishLabel.hidden = true;
    this.paint();
  }

  /** Colour every marker for what is lit, what is open and what is in focus, and place the rings and labels. */
  paint() {
    const colours = this.colours;
    if (!colours.plain) return;
    const tones = this.lens.tones;
    const rest = Boolean(this.opened); // while a family is open, the shelves stand back
    for (const node of this.nodes.values()) {
      const lit = this.lit(node.item);
      const hot = node.item.key === this.selected || node.item.key === this.hovered || node.item === this.opened;
      const show = (!rest && lit) || hot;
      // What is not shown sinks into what it stands on: the membrane's colour, or the page's.
      const dim = node.area === "plate" ? colours.sunk : colours.dim;
      if (node.mesh) node.mesh.setColorAt(node.index, show ? colours[node.tone] : dim);
      if (node.pip) node.pip.mesh.setColorAt(node.pip.index, show ? colours.unit : dim);
      if (node.foot) node.foot.mesh.setColorAt(node.foot.index, show ? colours.unit : dim);
      if (node.form) for (const mesh of node.form.meshes) mesh.material = tones.get(mesh.userData.tone)[show ? "lit" : "dim"];
      if (node.label) node.label.hidden = rest || !lit;
    }
    for (const mesh of this.meshes) if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true;
    // The names on the shelves give way to the open family's.
    for (const district of this.districts) if (district.tag) district.tag.hidden = rest;
    for (const label of this.notes || []) label.hidden = rest;
    const dish = this.dish;
    if (dish) {
      // A smaller family chosen within its gathering: its members alone are lit.
      const chosen = this.selected ? this.shelves.get(this.selected) : null;
      const only = chosen && chosen.within === dish.item ? chosen : null;
      for (const entry of dish.nodes.values()) {
        const hot = entry.item.key === this.selected || entry.item.key === this.hovered;
        const show = (this.lit(entry.item) && (!only || entry.item.under === only)) || hot;
        const dim = entry.zone === "plate" ? colours.sunk : colours.dim;
        if (entry.mesh) entry.mesh.setColorAt(entry.index, show ? (entry.shade && entry.tone === "plain" ? colours.plainAlt : colours[entry.tone]) : dim);
        if (entry.foot) entry.foot.mesh.setColorAt(entry.foot.index, show ? colours.unit : dim);
        if (entry.form) for (const mesh of entry.form.meshes) mesh.material = tones.get(mesh.userData.tone)[show ? "lit" : "dim"];
      }
      for (const mesh of dish.meshes) if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true;
    }
    this.place(this.ring, this.selected, this.hot?.selected);
    this.place(this.hoverRing, this.hovered && this.hovered !== this.selected ? this.hovered : null, this.hot?.hovered);
    if (this.dishLabel) {
      this.dishLabel.hidden = !dish;
      if (dish) {
        this.labelLayer.setText(this.dishLabel, `${dish.item.label} · ${plural(dish.count, "protein")}`);
        this.dishLabel.anchor.set(dish.to.x, dish.to.y + GLASS, dish.to.z + dish.reach + 2);
      }
    }
    this.stage.invalidate();
  }

  place(ring, key, label) {
    const node = key ? this.nodeOf(key) : null;
    // What is open is not ringed where it stood, nor is what stands within it: the open shelves say where they are.
    const item = key ? this.shelves.get(key) : null;
    const shown = Boolean(node) && !(this.dish && (item === this.dish.item || item?.within === this.dish.item));
    ring.visible = shown;
    if (label) label.hidden = !shown;
    if (!shown) return;
    ring.position.copy(node.ringAt);
    ring.scale.setScalar(node.radius + 0.75);
    if (label) {
      this.labelLayer.setText(label, this.hotText(key) || "");
      label.anchor.set(node.position.x, node.top + 0.5, node.position.z);
    }
  }

  /** Bring the camera to a protein that is drawn. A family is brought into view by its opening. */
  focus(key) {
    const item = this.shelves.get(key);
    const node = item?.type === "p" ? this.nodeOf(key) : null;
    if (!node || node.item !== item) return;
    const rig = this.stage.rig;
    rig.flyTo({ target: node.position.clone(), distance: Math.min(rig.distance, this.dish ? Math.max(40, this.dish.reach * 2.2) : 70), polar: Math.min(rig.polar, 1.02) }, 900);
  }

  /** The view that shows the whole stack from the front and above, clear of the page's card and notes. */
  home() {
    return this.frame("home");
  }

  /**
   * The view that shows the whole stack ("home") or the open family ("dish") within the
   * part of the screen that is free. It is remembered, so that the picture is framed again
   * when the window or the panel changes while the camera still stands there.
   */
  frame(of) {
    const stage = this.stage, narrow = stage.width < 760;
    const free = freeOf(stage, { panel: true });
    let view;
    if (of === "dish" && this.dish) {
      const { to, reach, high } = this.dish, r = reach + 2.5;
      view = fitView(stage, { minX: to.x - r, maxX: to.x + r, minY: to.y + GLASS - 1, maxY: to.y + high, minZ: to.z - r, maxZ: to.z + r }, { polar: narrow ? 0.62 : 0.74, azimuth: stage.rig.azimuth, free });
      view.distance = Math.max(view.distance, 56);
    } else {
      of = "home";
      view = fitView(stage, this.bounds, { polar: narrow ? 0.7 : 0.8, azimuth: narrow ? 0.1 : 0.16, free });
    }
    this.framing = { of, view, key: this.frameKey() };
    return view;
  }

  /** What a picture was framed for: the window and what the panel covers of it. */
  frameKey() {
    const { width, height, insets } = this.stage;
    return `${width}x${height}:${insets?.right || 0}:${insets?.bottom || 0}`;
  }

  /** Whether the camera stands at a view, or is on its way there. */
  rigAt(view) {
    const rig = this.stage.rig, now = rig.flight ? rig.flight.to : rig;
    return Math.abs(now.distance - view.distance) < 1e-3 && now.target.distanceTo(view.target) < 1e-3 && Math.abs(now.polar - view.polar) < 1e-4;
  }

  applyPalette(palette) {
    const named = new THREE.Color(palette.bioProtein), generic = new THREE.Color(palette.atlasGeneric), ground = new THREE.Color(palette.bg);
    const plain = generic.clone().lerp(palette.dark ? WHITE : BLACK, palette.dark ? 0.1 : 0.06);
    this.colours = {
      plain,
      plainAlt: plain.clone().lerp(palette.dark ? WHITE : BLACK, 0.24),
      more: plain.clone().lerp(palette.dark ? BLACK : WHITE, 0.34),
      unit: named,
      dim: plain.clone().lerp(ground, palette.dark ? 0.7 : 0.72),
      // On the membrane, towards the membrane's own face.
      sunk: plain.clone().lerp(new THREE.Color(palette.bioMembrane).lerp(palette.dark ? BLACK : WHITE, palette.dark ? 0.42 : 0.3), 0.8),
    };
    this.veilMaterial.color.copy(ground);
    this.materials.stalk.color.copy(plain).lerp(ground, 0.35);
    for (const sheet of [...this.sheets, this.dish?.sheet].filter(Boolean)) {
      const colour = new THREE.Color(palette.bioMembrane);
      sheet.body.color.copy(colour).lerp(BLACK, palette.dark ? 0.45 : 0);
      sheet.body.opacity = palette.dark ? 0.55 : 0.45;
      if (palette.dark) sheet.faces.color.copy(colour).lerp(BLACK, 0.42);
      else sheet.faces.color.copy(colour).lerp(WHITE, 0.3);
    }
    this.trayMaterial.color.set(palette.plate).lerp(WHITE, palette.dark ? 0.08 : 0.2);
    this.trayMaterial.opacity = palette.dark ? 0.34 : 0.42;
    this.lineMaterial.color.set(palette.edge);
    this.dashes.color.set(palette.ghost);
    this.ring.material.color.set(palette.fg);
    this.hoverRing.material.color.set(palette.fg);
    this.fill.intensity = palette.dark ? 0.8 : 0.55;
    this.paint();
  }

  /** How much is drawn: for the page's own account of its cost. */
  drawn() {
    const instances = (meshes) => meshes.reduce((sum, mesh) => sum + mesh.count, 0);
    return {
      markers: this.nodes.size,
      meshes: this.meshes.length,
      instances: instances(this.meshes),
      forms: this.forms.length,
      open: this.dish ? { members: this.dish.count, meshes: this.dish.meshes.length, instances: instances(this.dish.meshes), forms: this.dish.forms.length } : null,
    };
  }

  dispose() {
    for (const dish of [this.dish, this.leaving]) if (dish) this.drop(dish);
    disposeTree(this.group);
    for (const proto of this.protos.values()) disposeTree(proto.group);
    for (const material of [this.lineMaterial, this.dashes, this.trayMaterial, this.veilMaterial, ...Object.values(this.materials)]) material.dispose();
  }
}
