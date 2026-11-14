// The cell lens: what Cells can simulate, drawn where it happens. One cutaway cell,
// the sheet of cells around it, and outlines of the organ and organism it would
// belong to. Zooming is continuous: each scale fades in as the camera reaches it.
//
// Two things are encoded separately. Status (qualified, planned, ...) sets colour and
// form, as in the engine lens. Representation (simulated, modelled, prescribed) is
// stated in the panel; shapes that stand for modelled populations are illustrations.

import * as THREE from "../three.js";
import { statusToken } from "../core/theme.js";
import { glyphSprite } from "../core/materials.js";
import { disposeTree } from "../core/stage.js";
import { R, CUT_PLANES, MOLECULE_PATCH, HEX, ORGAN, BODY, buildCell, buildMolecules, buildTissue, buildOrgan, buildOrganism } from "./cell_parts.js";

const smooth = (a, b, x) => {
  const t = Math.min(1, Math.max(0, (x - a) / (b - a)));
  return t * t * (3 - 2 * t);
};
const WHITE = new THREE.Color(0xffffff), BLACK = new THREE.Color(0x000000);

// Camera distances at which each scale fades in and out.
const RANGES = {
  molecules: { out: [7, 13] },
  studs: { in: [6, 11], out: [120, 190] },
  cell: { out: [120, 190] },
  tissue: { in: [100, 190], out: [2400, 4200] },
  organ: { in: [2000, 4200], out: [34000, 52000] },
  organism: { in: [30000, 52000] },
};

/** One drawn thing bound to one entity of the scene. */
class Part {
  constructor(lens, entity, zone, anchor) {
    this.lens = lens;
    this.entity = entity;
    this.zone = zone;
    this.anchor = anchor || null;
    this.status = entity?.status || null;
    this.materials = [];
    this.group = new THREE.Group();
    if (entity) this.group.userData.pick = entity.id;
    else this.group.userData.unpickable = true;
    zone.root.add(this.group);
    zone.parts.push(this);
  }

  add(...objects) {
    this.group.add(...objects);
  }

  /** A material in this part's status look. shade lightens (+) or darkens (-) the status colour. */
  material({ opacity = 1, wire = false, shade = 0, emissive = 0, roughness = 0.6, flat = false, side = THREE.FrontSide, clip = false, depthWrite } = {}) {
    const sketch = wire || this.status === "planned";
    let material;
    if (sketch) {
      material = new THREE.MeshBasicMaterial({ wireframe: true, transparent: true, opacity: 0.6, depthWrite: false });
      opacity = 0.6;
    } else {
      if (this.status === "designed") opacity *= 0.45;
      material = new THREE.MeshStandardMaterial({
        roughness,
        metalness: 0,
        flatShading: flat,
        side,
        transparent: opacity < 1,
        opacity,
        depthWrite: depthWrite ?? opacity === 1,
      });
    }
    if (clip) {
      material.clippingPlanes = CUT_PLANES;
      material.clipIntersection = true;
    }
    material.userData = { base: opacity, shade, emissive, sketch, solidDepth: material.depthWrite };
    this.materials.push(material);
    return material;
  }

  colour(palette) {
    for (const material of this.materials) {
      const data = material.userData;
      const colour = new THREE.Color(data.sketch ? palette.ghost : palette[statusToken(this.status)]);
      if (data.shade > 0) colour.lerp(WHITE, data.shade);
      else if (data.shade < 0) colour.lerp(BLACK, -data.shade);
      material.color.copy(colour);
      data.tint = colour;
    }
  }

  /** dim: another part is in focus. hot: this part is under the pointer or selected. */
  look(fade, dim, hot) {
    for (const material of this.materials) {
      const data = material.userData;
      const opacity = data.base * fade * (dim ? 0.16 : 1);
      material.opacity = opacity;
      material.transparent = opacity < 0.999;
      material.depthWrite = data.solidDepth && opacity > 0.9;
      if (material.emissive && data.tint) material.emissive.copy(data.tint).multiplyScalar(data.emissive + (hot ? 0.28 : 0));
    }
  }
}

export class CellLens {
  constructor(stage, model, labels) {
    this.id = "cell";
    this.stage = stage;
    this.model = model;
    this.labels = labels;
    this.root = new THREE.Group();
    this.zones = {};
    this.byEntity = new Map(); // entity id -> [Part]
    this.neutrals = [];
    this.selected = null;
    this.hovered = null;
    this.isolate = null;
    this.together = null;
    this.activeStop = "cell";
    this.clock = 0;
    this.capabilityByPart = new Map(model.ofKind("capability").map((entity) => [entity.part, entity]));
    this.build();
    this.applyPalette(stage.palette);
  }

  // ------------------------------------------------------------ building

  build() {
    for (const name of Object.keys(RANGES)) {
      const zone = { name, root: new THREE.Group(), parts: [], neutrals: [], labels: [], fade: -1 };
      this.zones[name] = zone;
      this.root.add(zone.root);
    }
    const context = (zone) => ({
      part: (name, anchor) => this.bind(this.capabilityByPart.get(name), zone, anchor, name),
      scale: (id, anchor) => this.bind(this.model.get(id), zone, anchor, id),
      neutral: (options = {}) => this.neutral(zone, new THREE.MeshStandardMaterial({ roughness: 0.9, metalness: 0, transparent: true, side: options.side ?? THREE.FrontSide, depthWrite: options.depthWrite ?? false }), options),
      neutralLine: (options = {}) =>
        this.neutral(zone, options.dashed ? new THREE.LineDashedMaterial({ transparent: true, dashSize: 3, gapSize: 2.2 }) : new THREE.LineBasicMaterial({ transparent: true }), options),
      illustrate: (object, zoneName) => {
        object.userData.unpickable = true;
        (zoneName ? this.zones[zoneName] : zone).root.add(object);
      },
      sprite: (part, text, position, size) => {
        const sprite = glyphSprite(text, "#ffffff", size);
        sprite.position.copy(position);
        sprite.userData.unpickable = true;
        this.neutral(zone, sprite.material, { opacity: 0.85, colour: "fg" });
        part.add(sprite);
      },
    });
    buildCell(context(this.zones.cell), context(this.zones.studs));
    this.molecule = buildMolecules(context(this.zones.molecules));
    this.sheet = buildTissue(context(this.zones.tissue));
    buildOrgan(context(this.zones.organ));
    buildOrganism(context(this.zones.organism));
    this.stops = this.makeStops();
  }

  bind(entity, zone, anchor, name) {
    if (!entity) console.warn(`cell lens: nothing in the scene for "${name}"; drawn as neutral`);
    const part = new Part(this, entity, zone, anchor);
    if (entity) {
      if (!this.byEntity.has(entity.id)) this.byEntity.set(entity.id, []);
      this.byEntity.get(entity.id).push(part);
    }
    return part;
  }

  neutral(zone, material, { opacity = 0.5, colour = "ghost" } = {}) {
    material.userData = { base: opacity, colour };
    material.opacity = opacity;
    zone.neutrals.push(material);
    return material;
  }

  makeStops() {
    const entity = (id) => this.model.get(id);
    const out = this.molecule.outward;
    return [
      { id: "molecule", entity: entity("scale.molecule"), zone: "molecules", anchor: MOLECULE_PATCH.clone().addScaledVector(out, 1.05), size: [4.6, 3.0], target: MOLECULE_PATCH.clone(), azimuth: 0.12, polar: 1.42 },
      { id: "cell", entity: entity("scale.cell"), zone: "cell", anchor: new THREE.Vector3(0, R + 6.2, 0), size: [45, 38], target: new THREE.Vector3(0, 0.8, 0), azimuth: 0.75, polar: 1.02 },
      { id: "tissue", entity: entity("scale.tissue"), zone: "tissue", anchor: new THREE.Vector3(0, HEX.height * 2.6, -this.sheet.extent * 0.5), size: [this.sheet.extent * 1.42, this.sheet.extent * 1.0], target: new THREE.Vector3(0, -6, 0), azimuth: 0.55, polar: 0.86 },
      { id: "organ", entity: entity("scale.organ"), zone: "organ", size: [ORGAN.radius * 2.9, ORGAN.radius * 2.6], target: ORGAN.centre.clone(), azimuth: 0.6, polar: 1.08 },
      { id: "organism", entity: entity("scale.organism"), zone: "organism", size: [BODY.length * 1.3, BODY.length * 0.62], target: BODY.centre.clone(), azimuth: 0.25, polar: 1.12 },
    ];
  }

  /** The camera view that frames a stop on the current screen. */
  stopView(stop) {
    const { camera } = this.stage;
    const half = Math.tan((camera.fov * Math.PI) / 360);
    const distance = Math.max(stop.size[1] / (2 * half), stop.size[0] / (2 * half * camera.aspect));
    return { target: stop.target.clone(), distance, azimuth: stop.azimuth, polar: stop.polar };
  }

  // ------------------------------------------------------------ lens interface

  has(id) {
    return this.model.get(id)?.group === "biology";
  }

  entities() {
    return this.model.entities.filter((entity) => entity.group === "biology");
  }

  sections() {
    const capabilities = this.model.ofKind("capability");
    return [
      { label: "One cell", entities: capabilities.filter((entity) => entity.scale === "cell") },
      { label: "Tissue", entities: capabilities.filter((entity) => entity.scale === "tissue") },
      { label: "Scales", entities: this.model.ofKind("scale").sort((a, b) => a.order - b.order) },
    ];
  }

  chrome() {
    return {
      caveat: this.model.raw.caveat,
      rail: this.stops.map((stop) => ({ id: stop.id, label: stop.entity?.label || stop.id, title: stop.entity?.plain })),
      railActive: this.activeStop,
      together: (this.model.raw.model_groups || []).map((group) => ({ id: group.id, label: group.label, title: group.description })),
      togetherActive: this.together,
    };
  }

  get pickRoots() {
    return [this.root];
  }

  activate() {
    const { stage } = this;
    stage.scene.add(this.root);
    stage.sun.castShadow = false;
    stage.sun.position.set(60, 95, 85);
    stage.sun.target.position.set(0, 0, 0);
    stage.rig.limits = { minDistance: 2.4, maxDistance: 130000, minPolar: 0.12, maxPolar: 2.35 };
    stage.rig.setView(this.stopView(this.stops.find((stop) => stop.id === this.activeStop)));
    this.buildLabels();
    this.fades(true);
    this.refresh();
  }

  deactivate() {
    this.stage.scene.remove(this.root);
    this.labels.clear();
  }

  buildLabels() {
    const labels = this.labels;
    labels.clear();
    for (const zone of Object.values(this.zones)) zone.labels = [];
    for (const parts of this.byEntity.values()) {
      for (const part of parts) {
        if (!part.anchor) continue;
        const isScale = part.entity.kind === "scale";
        part.label = labels.add({ id: part.entity.id, text: part.entity.label, anchor: part.anchor, priority: isScale ? 300 : this.model.isBuilt(part.entity) ? 40 : 50, kind: isScale ? "scale" : "part", lift: isScale ? 4 : 9 });
        part.zone.labels.push(part.label);
      }
    }
    for (const stop of this.stops) {
      if (!stop.anchor || !stop.entity) continue;
      const label = labels.add({ id: stop.entity.id, text: stop.entity.label, anchor: stop.anchor, priority: 300, kind: "scale", lift: 4 });
      this.zones[stop.zone].labels.push(label);
    }
    const note = labels.add({ text: "Illustration: channels and pumps are modelled as populations", anchor: MOLECULE_PATCH.clone().addScaledVector(this.molecule.outward, 1.05), priority: 290, kind: "note", lift: -26 });
    this.zones.molecules.labels.push(note);
  }

  goToScale(id, immediate = false) {
    const stop = this.stops.find((item) => item.id === id);
    if (!stop) return;
    const view = this.stopView(stop);
    this.stage.rig.limits.minDistance = 2.4;
    if (immediate) this.stage.rig.setView(view);
    else this.stage.rig.flyTo(view, 1700);
    this.fades(true);
  }

  setSelection(id) {
    this.selected = id && this.has(id) ? id : null;
    this.refresh();
  }

  setHover(id) {
    const next = id && this.has(id) ? id : null;
    if (next === this.hovered) return;
    this.hovered = next;
    this.refresh();
  }

  setIsolate(status) {
    this.isolate = status || null;
    this.refresh();
  }

  setTogether(groupId) {
    this.together = groupId || null;
    this.refresh();
    this.onChrome?.();
  }

  lit(entity) {
    if (this.selected && entity.kind === "capability" && entity.id !== this.selected && this.model.get(this.selected)?.kind === "capability") return false;
    if (this.isolate && entity.status !== this.isolate) return false;
    if (this.together && entity.kind === "capability" && !(entity.runs_in || []).includes(this.together)) return false;
    return true;
  }

  refresh() {
    for (const [id, parts] of this.byEntity) {
      const entity = parts[0].entity;
      const lit = this.lit(entity);
      const hot = id === this.selected || id === this.hovered;
      for (const part of parts) {
        part.dim = !lit;
        part.hot = hot;
        part.look(Math.max(0, part.zone.fade), part.dim, part.hot);
        if (part.label) {
          part.label.boost = hot ? 1000 : 0;
          part.label.element.classList.toggle("is-dim", !lit);
          part.label.element.classList.toggle("is-focus", id === this.selected);
        }
      }
    }
    this.stage.invalidate();
  }

  focus(id) {
    const entity = this.model.get(id);
    if (!entity) return;
    if (entity.kind === "scale") {
      const stop = this.stops.find((item) => item.entity?.id === id);
      if (stop) this.goToScale(stop.id);
      return;
    }
    const part = (this.byEntity.get(id) || []).find((item) => item.zone.name !== "molecules") || this.byEntity.get(id)?.[0];
    if (!part) return;
    const stop = this.stops.find((item) => item.zone === (part.zone.name === "studs" ? "cell" : part.zone.name));
    const view = this.stopView(stop);
    if ((part.zone.name === "cell" || part.zone.name === "studs") && part.anchor) {
      view.target = part.anchor.clone().multiplyScalar(0.3);
      view.distance *= 0.82;
    }
    this.stage.rig.flyTo(view, 1300);
  }

  // ------------------------------------------------------------ fading between scales

  fades(force = false) {
    const distance = this.stage.rig.distance;
    let changed = false;
    for (const zone of Object.values(this.zones)) {
      const range = RANGES[zone.name];
      const fade = (range.in ? smooth(range.in[0], range.in[1], distance) : 1) * (range.out ? 1 - smooth(range.out[0], range.out[1], distance) : 1);
      if (!force && Math.abs(fade - zone.fade) < 0.004) continue;
      changed = true;
      zone.fade = fade;
      zone.root.visible = fade > 0.01;
      for (const part of zone.parts) part.look(fade, part.dim, part.hot);
      for (const material of zone.neutrals) {
        material.opacity = material.userData.base * fade;
        material.transparent = true;
      }
      for (const label of zone.labels) label.hidden = fade < 0.55;
    }
    // Which stop are we nearest to, on a log scale?
    let nearest = this.activeStop, best = Infinity;
    for (const stop of this.stops) {
      const gap = Math.abs(Math.log(distance) - Math.log(this.stopView(stop).distance));
      if (gap < best) {
        best = gap;
        nearest = stop.id;
      }
    }
    if (nearest !== this.activeStop) {
      this.activeStop = nearest;
      this.onChrome?.();
    }
    // Close to the membrane patch the camera may come near; at the cell's centre it stays outside the cell.
    this.stage.rig.limits.minDistance = R + 6 + (2.4 - R - 6) * smooth(0, R * 0.9, this.stage.rig.target.length());
    return changed;
  }

  update(dt) {
    const changed = this.fades();
    if (this.stage.reducedMotion) {
      this.animate(0.35);
      return changed;
    }
    const near = this.zones.cell.fade > 0.02 || this.zones.molecules.fade > 0.02;
    if (!near) return changed;
    this.clock += dt / 1000;
    this.animate(this.clock);
    return true;
  }

  /** Small motions that say what a part does: water crossing, signals leaving, ions through a channel. */
  animate(time) {
    const cell = (name) => this.byEntity.get(this.capabilityByPart.get(name)?.id)?.find((part) => part.zone.name === "cell");
    const water = cell("water");
    if (water?.streams) {
      water.streams.forEach((stream, which) => {
        stream.drops.forEach((drop, index) => {
          const t = (time * 0.22 + index / stream.drops.length + which * 0.31) % 1;
          const inward = which !== 1;
          drop.position.copy(stream.direction).multiplyScalar(R + (inward ? 1.6 - t * 3.0 : -1.4 + t * 3.0));
          drop.scale.setScalar(0.55 + 0.45 * Math.sin(Math.PI * t));
        });
      });
    }
    const secretion = cell("secretion");
    if (secretion?.beads) {
      secretion.beads.forEach((bead, index) => {
        const t = (time * 0.09 + index / secretion.beads.length) % 1;
        bead.position.copy(secretion.path(t));
        bead.scale.setScalar(0.5 + 0.7 * Math.sin(Math.PI * Math.min(1, t * 1.15)));
      });
    }
    const cage = cell("cage");
    if (cage?.spin) cage.spin.rotation.set(time * 0.25, time * 0.4, 0);
    const channel = this.byEntity.get(this.capabilityByPart.get("channels")?.id)?.find((part) => part.zone.name === "molecules");
    if (channel?.ions) {
      channel.ions.forEach((ion, index) => {
        const t = (time * 0.35 + index / channel.ions.length) % 1;
        ion.position.copy(channel.path(t));
      });
    }
  }

  applyPalette(palette) {
    for (const parts of this.byEntity.values()) for (const part of parts) part.colour(palette);
    for (const zone of Object.values(this.zones)) {
      for (const part of zone.parts) if (!part.entity) part.colour(palette);
      for (const material of zone.neutrals) material.color.set(palette[material.userData.colour] || palette.ghost);
    }
    this.refresh();
    this.fades(true);
  }

  dispose() {
    disposeTree(this.root);
  }
}
