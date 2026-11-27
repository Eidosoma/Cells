import * as THREE from "../three.js";
import { disposeTree } from "../core/stage.js";
import { emit, h } from "../ui/dom.js";
import { registerEntryView } from "../ui/entry_views.js";
import { fitView } from "./laws_marks.js";

const CUT_START = Math.PI * .84;
const CUT_LENGTH = Math.PI * 1.32;
const PLATE = new THREE.Vector3(2.12, .58, 1.6);
const ROD_RADIUS = .64;
const ROD_HALF = 1.425;
const PARTS = {
  "s-layer": {
    label: "S-layer",
    plain: "Repeating glycoprotein units coat the outside of the cytoplasmic membrane. The hexagonal marks illustrate their arrangement.",
    doors: [
      { label: "Inspect the deposited S-layer hexamer", lens: "machines", select: "machine:haloferax-s-layer" },
      { label: "Look up the S-layer glycoprotein", lens: "proteins", show: "own", find: "P25062" },
    ],
  },
  membrane: {
    label: "Cytoplasmic membrane",
    plain: "The membrane forms the cell's permeability barrier beneath the S-layer. The space between the two layers is shown enlarged.",
  },
  cytoplasm: {
    label: "Cytoplasm",
    plain: "The interior contains the archaeal ribosomes. The catalogue includes the 70S assembly with its bound hibernation factor.",
    doors: [{ label: "Inspect the 70S ribosome", lens: "machines", select: "machine:haloferax-70s-ribosome" }],
  },
  pilus: {
    label: "Type IV pilus",
    plain: "This surface filament is assembled from pilin subunits. The viewer illustrates a filament and links the experimental assembly.",
    doors: [{ label: "Inspect the deposited pilus", lens: "machines", select: "machine:haloferax-type-iv-pilus" }],
  },
};

const partId = (key) => `haloferax:${key}`;

function ellipsoid(size, cut = false) {
  return new THREE.SphereGeometry(1, 56, 30, cut ? CUT_START : 0, cut ? CUT_LENGTH : Math.PI * 2)
    .scale(size.x, size.y, size.z);
}

function lattice(material, sites) {
  const geometry = new THREE.RingGeometry(.055, .102, 6);
  const facing = new THREE.Vector3(0, 0, 1);
  const stamp = new THREE.Object3D();
  const mesh = new THREE.InstancedMesh(geometry, material, sites.length);
  sites.forEach(([position, normal], index) => {
    stamp.position.copy(position).addScaledVector(normal, .023);
    stamp.quaternion.setFromUnitVectors(facing, normal);
    stamp.updateMatrix();
    mesh.setMatrixAt(index, stamp.matrix);
  });
  mesh.userData.pick = partId("s-layer");
  return mesh;
}

/** Positions for the S-layer pattern on both faces of the plate. */
function plateSites(cut) {
  const sites = [];
  for (const direction of [-1, 1]) {
    for (let row = -8; row <= 8; row++) {
      for (let column = -10; column <= 10; column++) {
        const x = (column + (row & 1) * .5) * .20, z = row * .18;
        const u = x / PLATE.x, v = z / PLATE.z;
        if (u * u + v * v > .92) continue;
        const phi = (Math.atan2(v, -u) - CUT_START + 3 * Math.PI * 2) % (Math.PI * 2);
        if (cut && phi > CUT_LENGTH) continue;
        const w = direction * Math.sqrt(1 - u * u - v * v);
        const normal = new THREE.Vector3(u / PLATE.x, w / PLATE.y, v / PLATE.z).normalize();
        sites.push([new THREE.Vector3(x, w * PLATE.y, z), normal]);
      }
    }
  }
  return sites;
}

function rodSites() {
  const sites = [];
  for (let column = -10; column <= 10; column++) {
    const x = column * .19;
    const cap = Math.max(0, Math.abs(x) - ROD_HALF);
    const radius = Math.sqrt(ROD_RADIUS * ROD_RADIUS - cap * cap);
    const around = Math.round(2 * Math.PI * radius / .18);
    for (let row = 0; row < around; row++) {
      const angle = (row + (column & 1) * .5) * 2 * Math.PI / around;
      const y = radius * Math.cos(angle), z = radius * Math.sin(angle);
      sites.push([new THREE.Vector3(x, y, z), new THREE.Vector3(Math.sign(x) * cap, y, z).normalize()]);
    }
  }
  return sites;
}

export class HaloferaxLens {
  constructor(stage, labels, entry) {
    this.id = entry.id;
    this.stage = stage;
    this.labels = labels;
    this.entry = entry;
    this.level = "cell";
    this.form = "plate";
    this.wantsLeftRoom = true;
    this.root = new THREE.Group();
    this.figures = { plate: new THREE.Group(), rod: new THREE.Group(), envelope: new THREE.Group() };
    this.root.add(...Object.values(this.figures));
    this.materials = new Map();
    const material = (key, color, roughness) => {
      const body = new THREE.MeshStandardMaterial({ color, roughness, side: THREE.DoubleSide, emissive: color, emissiveIntensity: .05 });
      const materials = this.materials.get(key) || [];
      materials.push(body);
      this.materials.set(key, materials);
      return body;
    };
    const coat = material("s-layer", "#b85534", .52);
    const tile = material("s-layer", "#ffa970", .41);
    const membrane = material("membrane", "#e9aa42", .32);
    const fluid = material("cytoplasm", "#1b8d96", .43);
    const filament = material("pilus", "#f5c49d", .38);
    const add = (which, part, geometry, body) => {
      const mesh = new THREE.Mesh(geometry, body);
      mesh.userData.pick = partId(part);
      this.figures[which].add(mesh);
      return mesh;
    };
    add("plate", "s-layer", ellipsoid(PLATE), coat);
    this.figures.plate.add(lattice(tile, plateSites(false)));
    add("rod", "s-layer", new THREE.CapsuleGeometry(ROD_RADIUS, 2 * ROD_HALF, 12, 42).rotateZ(Math.PI / 2), coat);
    this.figures.rod.add(lattice(tile, rodSites()));
    const pilus = new THREE.CatmullRomCurve3([
      new THREE.Vector3(1.76, .36, .19), new THREE.Vector3(2.15, .53, .37),
      new THREE.Vector3(2.49, .78, .59), new THREE.Vector3(2.87, .74, .81),
    ]);
    add("rod", "pilus", new THREE.TubeGeometry(pilus, 40, .029, 8), filament);
    add("envelope", "s-layer", ellipsoid(PLATE, true), coat);
    this.figures.envelope.add(lattice(tile, plateSites(true)));
    add("envelope", "membrane", ellipsoid(new THREE.Vector3(1.96, .42, 1.44), true), membrane);
    add("envelope", "cytoplasm", ellipsoid(new THREE.Vector3(1.83, .30, 1.32)), fluid);
    this.anchors = {
      plate: { "s-layer": [0, .61, 0] },
      rod: { "s-layer": [-.56, .68, 0], pilus: [2.64, .78, .69] },
      envelope: { "s-layer": [-1.51, .43, -.06], membrane: [1.38, .28, .54], cytoplasm: [0, .14, 1.25] },
    };
    this.bounds = Object.fromEntries(Object.entries(this.figures).map(([id, figure]) => [id, new THREE.Box3().setFromObject(figure)]));
    this.sync();
  }

  get figure() { return this.level === "envelope" ? "envelope" : this.form; }
  get pickRoots() { return [this.figures[this.figure]]; }
  activate() {
    this.active = true;
    this.stage.scene.add(this.root);
    this.stage.dress?.({ rich: true, filmic: false, contact: false });
    this.stage.rig.limits = { minDistance: 2.3, maxDistance: 34, minPolar: .08, maxPolar: Math.PI - .08 };
    this.sync();
  }
  deactivate() {
    this.active = false;
    this.stage.scene.remove(this.root);
    this.stage.dress?.({ rich: false });
    this.labels.clear();
  }
  dispose() { disposeTree(this.root); }
  levels() { return this.entry.levels.map((level) => ({ ...level, active: level.id === this.level })); }
  setLevel(id) {
    if (id === this.level || !this.entry.levels.some((level) => level.id === id)) return;
    this.level = id;
    this.sync();
    this.onMode?.();
  }
  setMode(form) {
    if (this.level !== "cell" || form === this.form || !["plate", "rod"].includes(form)) return;
    this.form = form;
    this.sync();
    this.onMode?.();
  }
  sync() {
    for (const [id, group] of Object.entries(this.figures)) group.visible = id === this.figure;
    this.setSelection(null);
    if (!this.active) return;
    this.labels.clear();
    for (const [key, position] of Object.entries(this.anchors[this.figure])) {
      this.labels.add({ id: partId(key), text: PARTS[key].label, anchor: new THREE.Vector3(...position), priority: 700, lift: 9 });
    }
    this.frame();
  }
  frame() {
    const { width, height, camera, rig } = this.stage;
    const { left = 0, right = 0, bottom = 0 } = this.stage.insets || {};
    const rail = width > 760 && !right ? 188 : 0;
    const availableHeight = Math.max(150, height - bottom);
    const availableWidth = Math.max(150, width - left - right - rail);
    const half = Math.tan(camera.fov * Math.PI / 360);
    const fov = 2 * Math.atan(half * availableHeight / height) * 180 / Math.PI;
    this.room = [width, height, left, right, bottom].join("/");
    const view = fitView(this.bounds[this.figure], {
      fov, aspect: availableWidth / availableHeight, azimuth: this.figure === "envelope" ? .02 : this.form === "rod" ? -.13 : .26,
      polar: this.figure === "envelope" ? .89 : .57, margin: .18,
    });
    const across = new THREE.Vector3(Math.cos(view.azimuth), 0, -Math.sin(view.azimuth));
    view.target.addScaledVector(across, rail * view.distance * half / height);
    rig.setView(view);
  }
  update() {
    const { width, height, insets = {} } = this.stage;
    if ([width, height, insets.left || 0, insets.right || 0, insets.bottom || 0].join("/") !== this.room) this.frame();
    return false;
  }
  has(id) { return Object.keys(this.anchors[this.figure]).some((key) => partId(key) === id); }
  sections() {
    return [{ label: this.level === "cell" ? "Whole cell" : "Cell envelope",
      entities: Object.keys(this.anchors[this.figure]).map((key) => this.describe(partId(key))) }];
  }
  describe(id) {
    if (!this.has(id)) return null;
    const part = PARTS[id.slice(this.id.length + 1)];
    return { id, kind: "illustrated anatomy", eyebrow: "Haloferax · 3D illustration", ...part };
  }
  setSelection(id) {
    for (const [key, materials] of this.materials) for (const material of materials) material.emissiveIntensity = id === partId(key) ? .37 : .05;
    this.stage.invalidate();
  }
  chrome() {
    const open = (lens, annotations = {}) => emit(this.stage.canvas, "cells-door", { lens, ...annotations });
    return {
      caveat: "Anatomy illustration · schematic dimensions",
      card: {
        heading: this.entry.label,
        text: this.level === "cell" ? this.entry.plain : "Select a layer to inspect the membrane, S-layer or cytoplasm.",
        modes: this.level === "cell" ? { label: "Cell form", options: [["plate", "Plate"], ["rod", "Rod"]], active: this.form } : null,
        own: () => [h("div", { class: "haloferax-links" },
          h("button", { type: "button", class: "link-button", dataset: { haloferax: "proteins" }, onclick: () => open("proteins", { show: "own" }) }, "DS2 proteins"),
          h("button", { type: "button", class: "link-button", dataset: { haloferax: "machines" }, onclick: () => open("machines") }, "Molecular machines"))],
        sources: this.entry.modelled.record,
      },
      legend: false,
    };
  }
}

registerEntryView("haloferax", {
  label: "Haloferax",
  short: "Haloferax",
  make: (stage, model, labels, { entry }) => new HaloferaxLens(stage, labels, entry),
  styles: { shadow: ".haloferax-links {display:flex; flex-wrap:wrap; gap:6px 12px; padding-block:4px} @media (max-width:760px) {.haloferax-links button {min-height:40px}}" },
});
