import * as THREE from "../three.js";
import { enrich } from "../core/materials.js";
import { disposeTree } from "../core/stage.js";
import { emit, h } from "../ui/dom.js";
import { registerEntryView } from "../ui/entry_views.js";
import { fitView } from "./laws_marks.js";

import { lightSpecimen } from "./parts/illustration.js";
import { buildHaloferax } from "./parts/haloferax_anatomy.js";

const PARTS = {
  "s-layer": {
    label: "S-layer",
    plain: "Repeating glycoprotein units coat the outside of the cytoplasmic membrane. Raised six-lobed motifs illustrate the coat. Open the deposited hexamer to inspect its six protein chains.",
    doors: [
      { label: "Compare the measured membrane-to-coat spacing", lens: "machines", select: "organelle:envelope-section" },
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
  ribosome: {
    label: "70S ribosome",
    plain: "The paired shapes mark the two ribosomal subunits. Their positions and number are illustrative. The Machines bench shows the experimental Haloferax assembly.",
    doors: [{ label: "Inspect the deposited 70S ribosome", lens: "machines", select: "machine:haloferax-70s-ribosome" }],
  },
  pilus: {
    label: "Type IV pilus",
    plain: "This surface filament is assembled from pilin subunits. The viewer illustrates a filament and links the experimental assembly.",
    doors: [{ label: "Inspect the deposited pilus", lens: "machines", select: "machine:haloferax-type-iv-pilus" }],
  },
};

const partId = (key) => `haloferax:${key}`;

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
    const material = (key, color, roughness, vertexColors = false) => {
      const body = new THREE.MeshStandardMaterial({ color: vertexColors ? "#ffffff" : color, vertexColors, roughness, side: THREE.DoubleSide, emissive: color, emissiveIntensity: .05 });
      if (stage.numbers && (vertexColors || key === "membrane")) {
        enrich(body, stage.numbers, {rim:.085, thin:key === "membrane" ? .25 : .05, texture:"grain", unit:.2});
      }
      const materials = this.materials.get(key) || [];
      materials.push(body);
      this.materials.set(key, materials);
      return body;
    };
    this.anchors = buildHaloferax((which, key, mesh) => {
      mesh.userData.pick = partId(key);
      this.figures[which].add(mesh);
    }, {
      coat:material("s-layer","#984e50",.48,true), tile:material("s-layer","#ea9984",.38),
      coatEdge:material("s-layer","#a85651",.49), membrane:material("membrane","#e8ac50",.34),
      lipidCore:material("membrane","#82513a",.54), lipidHead:material("membrane","#ffe09a",.35),
      fluid:material("cytoplasm","#316e73",.52,true), speck:material("cytoplasm","#73a39a",.47),
      largeSubunit:material("ribosome","#a1b7bf",.40), smallSubunit:material("ribosome","#d6c2a1",.37),
      filament:material("pilus","#b76857",.38),
    });
    this.bounds = Object.fromEntries(Object.entries(this.figures).map(([id, figure]) => [id, new THREE.Box3().setFromObject(figure)]));
    this.sync();
  }

  get figure() { return this.level === "envelope" ? "envelope" : this.form; }
  get pickRoots() { return [this.figures[this.figure]]; }
  activate() {
    this.active = true;
    this.stopLook ??= this.stage.look?.onChange?.(() => { if (this.active) lightSpecimen(this); });
    this.stage.scene.add(this.root);
    this.stage.dress?.({ rich: true, filmic: true, exposure: 1.04, contact: true, reach: .095, shade: .33 });
    this.stage.rig.limits = { minDistance: 2.3, maxDistance: 34, minPolar: .08, maxPolar: Math.PI - .08 };
    lightSpecimen(this);
    this.sync();
  }
  applyPalette() { if (this.active) lightSpecimen(this); }
  deactivate() {
    this.active = false;
    this.stage.scene.remove(this.root);
    this.stage.dress?.({ rich: false });
    this.stage.scene.environment = null;
    this.stage.applyPalette?.();
    this.labels.clear();
  }
  dispose() {
    this.root.traverse(object => { if (object.isInstancedMesh) object.dispose(); });
    this.stopLook?.();
    this.studio?.dispose();
    disposeTree(this.root);
  }
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
      this.labels.add({ id: partId(key), text: PARTS[key].label, anchor: position, priority: 700, lift: 9 });
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
      fov, aspect: availableWidth / availableHeight, azimuth: this.figure === "envelope" ? -.35 : this.form === "rod" ? -.33 : .41,
      polar: this.figure === "envelope" ? .83 : .91, margin: .12,
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
        text: this.level === "cell" ? this.entry.plain : "Follow the rose S-layer down to the gold membrane. The paired particles on the exposed cytoplasm are ribosomes.",
        modes: this.level === "cell" ? { label: "Cell form", options: [["plate", "Plate"], ["rod", "Rod"]], active: this.form } : null,
        own: () => [h("div", { class: "haloferax-links" },
          h("button", { type: "button", class: "link-button", dataset: { haloferax: "proteins" }, onclick: () => open("proteins", { show: "own" }) }, "DS2 proteins"),
          h("button", { type: "button", class: "link-button", dataset: { haloferax: "shelf" }, onclick: () => open("machines", {select:"organelle:cell-bridge"}) }, "Cell structures shelf"),
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
