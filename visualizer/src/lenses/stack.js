// The engine lens: the simulator as a stack of layers, from the machines it runs on
// up to the experiments that use it. References stand outside the stack, because the
// engine never contains them; the plan's gates climb beside it as a ladder.

import * as THREE from "../three.js";
import { StatusMaterials, STATUS_ORDER, formOf, roundedSlab, linkCurve, glyphSprite } from "../core/materials.js";
import { disposeTree } from "../core/stage.js";

const NODE = { w: 3.7, d: 2.4, gapX: 0.85, gapZ: 0.95 };
const PLATE_PAD = 1.5;
const LEVEL = 8.6;
const SEMANTIC_KINDS = new Set(["requires", "writes", "provides", "reads", "conflicts", "wraps", "runs", "compared_with", "runs_on", "extends", "delivers", "operator_of"]);
const KIND_TOKEN = {
  requires: "kindRequires", reads: "kindRequires", uses: "kindRequires", operator_of: "kindRequires", wraps: "kindRequires", runs_on: "kindRequires",
  writes: "kindWrites", provides: "kindWrites",
  conflicts: "kindConflicts",
  runs: "kindRuns", compared_with: "kindRuns",
  extends: "kindExtends", delivers: "kindExtends",
};

export class StackLens {
  constructor(stage, model, labels) {
    this.id = "engine";
    this.stage = stage;
    this.model = model;
    this.labels = labels;
    this.root = new THREE.Group();
    this.materials = new StatusMaterials();
    this.nodes = new Map(); // id -> { entity, group, fill, outline, position, top }
    this.selected = null;
    this.hovered = null;
    this.isolate = null;
    this.build();
    this.applyPalette(stage.palette);
  }

  // ------------------------------------------------------------ layout

  build() {
    const model = this.model;
    const stackGroups = model.groups.filter((group) => group.placement === "stack").sort((a, b) => a.order - b.order);
    const layouts = stackGroups.map((group) => this.grid(this.sorted(model.inGroup(group.id)), 7));
    const width = Math.max(...layouts.map((layout) => layout.width)) + PLATE_PAD * 2;
    const depth = Math.max(...layouts.map((layout) => layout.depth)) + PLATE_PAD * 2;
    this.tower = { width, depth, height: (stackGroups.length - 1) * LEVEL };
    this.plateMaterial = new THREE.MeshStandardMaterial({ roughness: 0.95, metalness: 0, transparent: true, opacity: 0.74 });
    this.plateEdge = new THREE.LineBasicMaterial({ transparent: true, opacity: 0.9 });
    this.plates = [];

    stackGroups.forEach((group, level) => {
      const origin = new THREE.Vector3(0, level * LEVEL, 0);
      this.plate(group, origin, width, depth, new THREE.Vector3(-width / 2 + 0.6, 0.2, depth / 2 - 0.2));
      this.place(layouts[level], origin);
    });

    this.postMaterial = new THREE.LineBasicMaterial({ transparent: true, opacity: 0.55 });
    const posts = [];
    for (const [x, z] of [[-1, -1], [1, -1], [1, 1], [-1, 1]]) {
      posts.push((x * width) / 2 - x * 0.9, -0.26, (z * depth) / 2 - z * 0.9, (x * width) / 2 - x * 0.9, this.tower.height, (z * depth) / 2 - z * 0.9);
    }
    const postGeometry = new THREE.BufferGeometry();
    postGeometry.setAttribute("position", new THREE.Float32BufferAttribute(posts, 3));
    const postLines = new THREE.LineSegments(postGeometry, this.postMaterial);
    postLines.userData.unpickable = true;
    this.root.add(postLines);

    const left = model.groups.find((group) => group.placement === "left");
    if (left) {
      const layout = this.grid(this.sorted(model.inGroup(left.id)), 3);
      const w = layout.width + PLATE_PAD * 2, d = layout.depth + PLATE_PAD * 2;
      const origin = new THREE.Vector3(-(width / 2 + 9 + w / 2), 3.4 * LEVEL, depth * 0.55);
      this.plate(left, origin, w, d, new THREE.Vector3(-w / 2 + 0.6, 0.2, d / 2 - 0.2));
      this.place(layout, origin);
      this.sideBox = { min: origin.x - w / 2 };
    }

    const right = model.groups.find((group) => group.placement === "right");
    if (right) this.ladder(right, width);

    this.buildLinks();
    this.buildMarkers();
  }

  sorted(entities) {
    const rank = (entity) => STATUS_ORDER.indexOf(entity.status ?? null);
    return [...entities].sort((a, b) => rank(a) - rank(b) || (b.weight || 0) - (a.weight || 0) || a.label.localeCompare(b.label));
  }

  grid(entities, maxColumns) {
    const count = entities.length;
    const columns = Math.max(1, Math.min(maxColumns, Math.ceil(Math.sqrt(count * 2.6))));
    const rows = Math.ceil(count / columns);
    const width = columns * (NODE.w + NODE.gapX) - NODE.gapX;
    const depth = rows * (NODE.d + NODE.gapZ) - NODE.gapZ;
    const cells = entities.map((entity, index) => {
      const column = index % columns, row = Math.floor(index / columns);
      const inRow = row === rows - 1 ? count - row * columns : columns;
      const rowWidth = inRow * (NODE.w + NODE.gapX) - NODE.gapX;
      return {
        entity,
        x: -rowWidth / 2 + column * (NODE.w + NODE.gapX) + NODE.w / 2,
        z: -depth / 2 + row * (NODE.d + NODE.gapZ) + NODE.d / 2,
      };
    });
    return { cells, width, depth };
  }

  plate(group, origin, width, depth, labelAt) {
    const slab = new THREE.Mesh(roundedSlab(width, depth, 1.1, 0.04), this.plateMaterial);
    slab.scale.y = 0.26;
    slab.position.copy(origin).y -= 0.26;
    slab.userData.blocker = true;
    const outline = new THREE.LineSegments(new THREE.EdgesGeometry(slab.geometry, 30), this.plateEdge);
    outline.userData.unpickable = true;
    outline.scale.copy(slab.scale);
    outline.position.copy(slab.position);
    this.root.add(slab, outline);
    this.plates.push({ group, origin, width, depth, anchor: origin.clone().add(labelAt) });
  }

  place(layout, origin) {
    for (const cell of layout.cells) this.node(cell.entity, new THREE.Vector3(origin.x + cell.x, origin.y, origin.z + cell.z));
  }

  ladder(group, towerWidth) {
    const gates = this.model.inGroup(group.id).sort((a, b) => (a.order ?? 0) - (b.order ?? 0));
    const x = towerWidth / 2 + 8.5;
    const step = gates.length > 1 ? this.tower.height / (gates.length - 1) : 0;
    this.railMaterial = new THREE.MeshStandardMaterial({ roughness: 0.8 });
    for (const z of [-2.1, 2.1]) {
      const rail = new THREE.Mesh(new THREE.CylinderGeometry(0.11, 0.11, this.tower.height + 3, 10), this.railMaterial);
      rail.position.set(x, this.tower.height / 2, z);
      rail.userData.unpickable = true;
      this.root.add(rail);
    }
    gates.forEach((gate, index) => {
      const position = new THREE.Vector3(x, index * step, 0);
      const rung = new THREE.Mesh(new THREE.BoxGeometry(0.2, 0.2, 4.2), this.railMaterial);
      rung.position.copy(position).y -= 0.12;
      rung.userData.unpickable = true;
      this.root.add(rung);
      this.node(gate, position);
    });
    this.ladderInfo = { group, anchor: new THREE.Vector3(x, this.tower.height + 3.2, 0), x };
  }

  // ------------------------------------------------------------ nodes

  node(entity, position) {
    const status = entity.status || "unstated";
    const set = this.materials.get(status);
    const form = formOf(status);
    const group = new THREE.Group();
    group.position.copy(position);
    group.userData.pick = entity.id;
    group.userData.seeThrough = status === "planned";

    let geometry, height;
    if (entity.kind === "gate") {
      geometry = StackLens.shapes.gate;
      height = 0.8;
    } else if (entity.kind === "state") {
      geometry = StackLens.shapes.state;
      height = 0.9;
    } else if (status === "external") {
      geometry = StackLens.shapes.external;
      height = 1.0;
    } else {
      geometry = StackLens.shapes.block;
      height = entity.weight ? Math.min(2.7, 0.75 + 0.62 * Math.log10(1 + entity.weight / 150)) : 0.95;
    }
    this.gateMaterial ??= { lit: new THREE.MeshStandardMaterial({ roughness: 0.7 }), dim: new THREE.MeshStandardMaterial({ roughness: 0.9, transparent: true, opacity: 0.2, depthWrite: false }) };
    const fill = new THREE.Mesh(geometry, entity.kind === "gate" ? this.gateMaterial.lit : set.fill);
    fill.scale.y = height;
    group.add(fill);
    if (form.fill === 1 && entity.kind !== "gate") {
      const shade = new THREE.Mesh(StackLens.shapes.shade, this.shadeMaterial());
      shade.rotation.x = -Math.PI / 2;
      shade.position.y = 0.02;
      shade.userData.unpickable = true;
      group.add(shade);
    }

    let outline = null;
    if (form.outline) {
      outline = new THREE.LineSegments(StackLens.edges(geometry), set.line);
      outline.scale.y = height;
      if (form.outline === "dashed") outline.computeLineDistances();
      group.add(outline);
    }
    if (form.cross) group.add(this.cross(height));
    if (entity.kind === "gate") {
      this.gateNumbers ??= [];
      this.gateNumbers.push({ group, text: String((entity.order ?? 0) + 1), height });
    }
    this.root.add(group);
    this.nodes.set(entity.id, { entity, group, fill, outline, status, height, top: position.clone().setY(position.y + height) });
  }

  shadeMaterial() {
    if (!this.shade) {
      const canvas = document.createElement("canvas");
      canvas.width = canvas.height = 128;
      const context = canvas.getContext("2d");
      const gradient = context.createRadialGradient(64, 64, 18, 64, 64, 64);
      gradient.addColorStop(0, "rgba(0,0,0,0.55)");
      gradient.addColorStop(0.6, "rgba(0,0,0,0.22)");
      gradient.addColorStop(1, "rgba(0,0,0,0)");
      context.fillStyle = gradient;
      context.fillRect(0, 0, 128, 128);
      this.shade = new THREE.MeshBasicMaterial({ map: new THREE.CanvasTexture(canvas), transparent: true, depthWrite: false, opacity: 0.5 });
    }
    return this.shade;
  }

  cross(height) {
    const cross = new THREE.Group();
    this.crossMaterial ??= new THREE.MeshBasicMaterial({ color: 0xffffff });
    for (const turn of [Math.PI / 4, -Math.PI / 4]) {
      const bar = new THREE.Mesh(new THREE.BoxGeometry(2.3, 0.07, 0.3), this.crossMaterial);
      bar.rotation.y = turn;
      cross.add(bar);
    }
    cross.position.y = height + 0.06;
    cross.userData.unpickable = false;
    return cross;
  }

  static edges(geometry) {
    StackLens.edgeCache ??= new Map();
    if (!StackLens.edgeCache.has(geometry)) StackLens.edgeCache.set(geometry, new THREE.EdgesGeometry(geometry, 30));
    return StackLens.edgeCache.get(geometry);
  }

  // ------------------------------------------------------------ links

  buildLinks() {
    const faint = [], firm = [];
    this.curves = [];
    for (const relation of this.model.relations) {
      const from = this.nodes.get(relation.from), to = this.nodes.get(relation.to);
      if (!from || !to) continue;
      const curve = linkCurve(from.top, to.top);
      this.curves.push({ relation, curve });
      const points = curve.getPoints(14);
      const target = SEMANTIC_KINDS.has(relation.kind) ? firm : faint;
      for (let index = 0; index < points.length - 1; index++) {
        target.push(points[index].x, points[index].y, points[index].z, points[index + 1].x, points[index + 1].y, points[index + 1].z);
      }
    }
    this.webFaint = this.web(faint, 0.1);
    this.webFirm = this.web(firm, 0.3);
    this.focusLinks = new THREE.Group();
    this.root.add(this.focusLinks);
  }

  web(positions, opacity) {
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
    const lines = new THREE.LineSegments(geometry, new THREE.LineBasicMaterial({ transparent: true, opacity, depthWrite: false }));
    lines.userData.unpickable = true;
    lines.userData.opacity = opacity;
    this.root.add(lines);
    return lines;
  }

  buildMarkers() {
    // One ring that marks the part in focus, and a lighter one for the part under the pointer.
    this.ring = new THREE.Mesh(new THREE.TorusGeometry(2.45, 0.09, 8, 48), new THREE.MeshBasicMaterial());
    this.ring.rotation.x = Math.PI / 2;
    this.ring.visible = false;
    this.hoverRing = new THREE.Mesh(new THREE.TorusGeometry(2.45, 0.05, 8, 48), new THREE.MeshBasicMaterial({ transparent: true, opacity: 0.7 }));
    this.hoverRing.rotation.x = Math.PI / 2;
    this.hoverRing.visible = false;
    for (const ring of [this.ring, this.hoverRing]) ring.userData.unpickable = true;
    this.root.add(this.ring, this.hoverRing);
  }

  showFocusLinks(id) {
    for (const child of [...this.focusLinks.children]) {
      child.geometry.dispose();
      this.focusLinks.remove(child);
    }
    if (!id) return;
    const palette = this.stage.palette;
    const mine = this.curves.filter(({ relation }) => relation.from === id || relation.to === id);
    // Code imports can be many; draw the strongest and leave the rest in the faint web.
    const uses = mine.filter(({ relation }) => relation.kind === "uses").sort((a, b) => b.relation.weight - a.relation.weight).slice(0, 16);
    const chosen = [...mine.filter(({ relation }) => relation.kind !== "uses"), ...uses];
    for (const { relation, curve } of chosen) {
      const colour = palette[KIND_TOKEN[relation.kind] || "kindRequires"];
      const material = this.linkMaterial(colour);
      const tube = new THREE.Mesh(new THREE.TubeGeometry(curve, 28, relation.kind === "uses" ? 0.05 : 0.085, 6), material);
      tube.userData.unpickable = true;
      this.focusLinks.add(tube);
      if (this.model.kinds.get(relation.kind)?.directed !== false) {
        const head = new THREE.Mesh(StackLens.shapes.arrow, material);
        const end = curve.getPoint(0.94);
        head.position.copy(end);
        head.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), curve.getTangent(0.94).normalize());
        head.userData.unpickable = true;
        this.focusLinks.add(head);
      }
    }
  }

  linkMaterial(colour) {
    this.linkMaterials ??= new Map();
    if (!this.linkMaterials.has(colour)) this.linkMaterials.set(colour, new THREE.MeshBasicMaterial({ color: colour }));
    return this.linkMaterials.get(colour);
  }

  // ------------------------------------------------------------ lens interface

  has(id) {
    return this.nodes.has(id);
  }

  entities() {
    return [...this.nodes.values()].map((node) => node.entity);
  }

  /** The parts as a list, top of the stack first, then the references and the plan. */
  sections() {
    const order = (group) => (group.placement === "stack" ? -group.order : group.placement === "left" ? 100 : 200);
    return [...this.model.groups]
      .sort((a, b) => order(a) - order(b))
      .map((group) => ({ label: group.label, entities: this.sorted(this.model.inGroup(group.id)).filter((entity) => this.nodes.has(entity.id)) }))
      .filter((section) => section.entities.length);
  }

  chrome() {
    return {};
  }

  get pickRoots() {
    return [this.root];
  }

  activate() {
    const { stage, tower } = this;
    stage.scene.add(this.root);
    stage.sun.castShadow = false;
    stage.sun.position.set(tower.width * 0.9, tower.height + 60, tower.depth * 3 + 30);
    stage.sun.target.position.set(0, tower.height / 2, 0);
    stage.rig.limits = { minDistance: 10, maxDistance: 520, minPolar: 0.25, maxPolar: Math.PI / 2 - 0.03 };
    stage.rig.setView(this.homeView());
    this.buildLabels();
    this.refresh();
  }

  deactivate() {
    this.stage.scene.remove(this.root);
    this.labels.clear();
  }

  homeView() {
    const { stage, tower } = this;
    const narrow = stage.width < stage.height * 0.9;
    // On a narrow screen frame the tower alone; the references and the ladder are a swipe away.
    const left = narrow ? -tower.width / 2 - 2 : this.sideBox?.min ?? -tower.width / 2;
    const right = narrow ? tower.width / 2 + 2 : (this.ladderInfo?.x ?? tower.width / 2) + 4;
    const spanX = right - left, spanY = tower.height + 9;
    const half = Math.tan((stage.camera.fov * Math.PI) / 360);
    const distance = Math.max(spanY / (2 * half), spanX / (2 * half * stage.camera.aspect)) * 1.06 + tower.depth * 0.6;
    return {
      target: new THREE.Vector3((left + right) / 2, tower.height / 2 + 0.5, 0),
      distance,
      azimuth: narrow ? 0.42 : 0.5,
      polar: 1.2,
    };
  }

  buildLabels() {
    const labels = this.labels;
    labels.clear();
    for (const plate of this.plates) {
      labels.add({ text: plate.group.label, anchor: plate.anchor, priority: 500, kind: "layer", lift: 2 });
    }
    if (this.ladderInfo) labels.add({ text: this.ladderInfo.group.label, anchor: this.ladderInfo.anchor, priority: 500, kind: "layer", lift: 2 });
    for (const node of this.nodes.values()) {
      const entity = node.entity;
      const degree = this.model.links(entity.id).filter((link) => link.relation.kind !== "uses").length;
      const priority = (entity.kind === "gate" ? 80 : 0) + (this.model.isBuilt(entity) ? 0 : 12) + 16 * Math.log2(1 + degree) + Math.min(12, Math.log10(1 + (entity.weight || 0)) * 3);
      node.label = labels.add({ id: entity.id, text: entity.label, anchor: node.top, priority, kind: "part", lift: 9 });
    }
  }

  setSelection(id) {
    this.selected = id && this.nodes.has(id) ? id : null;
    this.refresh();
  }

  setHover(id) {
    const next = id && this.nodes.has(id) ? id : null;
    if (next === this.hovered) return;
    this.hovered = next;
    this.refresh();
  }

  setIsolate(status) {
    this.isolate = status;
    this.refresh();
  }

  /** Recompute which parts are lit, dimmed and labelled. */
  refresh() {
    const focus = this.selected;
    const near = focus ? this.model.neighbours(focus) : null;
    for (const [id, node] of this.nodes) {
      let lit = true;
      if (focus) lit = id === focus || near.has(id);
      if (this.isolate !== null && this.isolate !== undefined) lit = lit && (node.status === this.isolate);
      const set = node.entity.kind === "gate" ? { fill: this.gateMaterial.lit, dim: this.gateMaterial.dim } : this.materials.get(node.status);
      node.fill.material = lit ? set.fill : set.dim;
      if (node.outline) node.outline.material = lit ? set.line : set.lineDim;
      if (node.label) {
        node.label.boost = id === focus || id === this.hovered ? 1000 : focus && near.has(id) ? 200 : 0;
        // With a part in focus, only it and its connections keep their names.
        node.label.hidden = !lit && id !== this.hovered;
        node.label.element.classList.toggle("is-focus", id === focus);
      }
    }
    this.mark(this.ring, focus);
    this.mark(this.hoverRing, this.hovered && this.hovered !== focus ? this.hovered : null);
    this.showFocusLinks(focus);
    const quiet = Boolean(focus) || (this.isolate !== null && this.isolate !== undefined);
    this.webFaint.material.opacity = quiet ? 0.035 : this.webFaint.userData.opacity;
    this.webFirm.material.opacity = quiet ? 0.07 : this.webFirm.userData.opacity;
    this.stage.invalidate();
  }

  mark(ring, id) {
    const node = id ? this.nodes.get(id) : null;
    ring.visible = Boolean(node);
    if (node) ring.position.copy(node.group.position).y += 0.12;
  }

  focus(id) {
    const node = this.nodes.get(id);
    if (!node) return;
    const rig = this.stage.rig;
    const home = this.homeView();
    // Close enough to read the part and its links, far enough to keep the stack in view.
    rig.flyTo({ target: node.top.clone().lerp(home.target, 0.35), distance: Math.min(rig.distance, Math.max(70, home.distance * 0.62)) });
  }

  update() {
    return false;
  }

  applyPalette(palette) {
    this.materials.applyPalette(palette);
    this.plateMaterial.color.set(palette.plate);
    this.plateEdge.color.set(palette.plateEdge);
    this.railMaterial?.color.set(palette.ghost);
    this.postMaterial.color.set(palette.plateEdge);
    if (this.gateMaterial) {
      this.gateMaterial.lit.color.set(palette.fg);
      this.gateMaterial.dim.color.set(palette.fg);
      // Numbers are drawn in the page colour, so they read on the dark markers in either theme.
      for (const gate of this.gateNumbers || []) {
        if (gate.sprite) {
          gate.group.remove(gate.sprite);
          gate.sprite.material.map.dispose();
          gate.sprite.material.dispose();
        }
        gate.sprite = glyphSprite(gate.text, palette.bgRaised, 1.5);
        gate.sprite.position.set(0, gate.height + 0.05, 0);
        gate.sprite.material.depthTest = false;
        gate.sprite.renderOrder = 5;
        gate.sprite.userData.unpickable = true;
        gate.group.add(gate.sprite);
      }
    }
    this.webFaint.material.color.set(palette.edge);
    this.webFirm.material.color.set(palette.edge);
    this.ring.material.color.set(palette.fg);
    this.hoverRing.material.color.set(palette.fg);
    this.crossMaterial?.color.set(palette.dark ? 0x0f1b27 : 0xffffff);
    this.shadeMaterial().opacity = palette.dark ? 0.75 : 0.42;
    this.linkMaterials = new Map();
    if (this.selected) this.showFocusLinks(this.selected);
  }

  dispose() {
    disposeTree(this.root);
    this.materials.dispose();
  }
}

StackLens.shapes = {
  block: roundedSlab(NODE.w, NODE.d, 0.42),
  state: new THREE.CylinderGeometry(1.45, 1.45, 1, 40).translate(0, 0.5, 0),
  gate: new THREE.CylinderGeometry(1.75, 1.75, 1, 6).translate(0, 0.5, 0),
  external: new THREE.CylinderGeometry(1.25, 1.45, 1, 8).translate(0, 0.5, 0),
  arrow: new THREE.ConeGeometry(0.26, 0.75, 10),
  shade: new THREE.PlaneGeometry(NODE.w * 1.55, NODE.d * 1.75),
};
