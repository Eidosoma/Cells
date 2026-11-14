// The cell lens: what Cells can simulate, drawn where it happens. One cell opened by
// a flat cut, the sheet of cells around it, and outlines of the organ and organism it
// would belong to. Zooming is continuous: each scale fades in as the camera reaches it.
//
// Three things are kept apart:
//   status          built parts are solid, planned parts are sketches; the exact status
//                   is the dot beside each name (or the colour, with "Colour: Status");
//   representation  simulated, modelled or prescribed: stated in the panel;
//   size mode       "schematic" enlarges parts so each can be seen; "real" draws sizes
//                   and numbers nearer a real cell, with dots for what is too small.

import * as THREE from "../three.js";
import { statusToken } from "../core/theme.js";
import { glyphSprite, soften } from "../core/materials.js";
import { disposeTree } from "../core/stage.js";
import { R, CUT, RIM, CUT_PLANES, HEX, ORGAN, BODY, buildCell, buildMolecules, buildTissue, buildOrgan, buildOrganism } from "./cell_parts.js";

const smooth = (a, b, x) => {
  const t = Math.min(1, Math.max(0, (x - a) / (b - a)));
  return t * t * (3 - 2 * t);
};
const WHITE = new THREE.Color(0xffffff), BLACK = new THREE.Color(0x000000);
export const SIZE_MODES = ["schematic", "real"];

// Camera distances (in micrometres) at which each scale fades in and out.
const RANGES = {
  schematic: { molecules: { out: [7, 13] }, studs: { out: [120, 190] }, cell: { out: [120, 190] } },
  real: { molecules: { out: [0.45, 1.2] }, studs: { in: [0.5, 1.6], out: [120, 190] }, cell: { out: [120, 190] } },
  shared: { tissue: { in: [100, 190], out: [2400, 4200] }, organ: { in: [2000, 4200], out: [34000, 52000] }, organism: { in: [30000, 52000] } },
};

let roundDot = null;
/** A soft round dot for point clouds, drawn once. */
function dotTexture() {
  if (!roundDot) {
    const canvas = document.createElement("canvas");
    canvas.width = canvas.height = 32;
    const context = canvas.getContext("2d");
    context.fillStyle = "#ffffff";
    context.beginPath();
    context.arc(16, 16, 13, 0, Math.PI * 2);
    context.fill();
    roundDot = new THREE.CanvasTexture(canvas);
  }
  return roundDot;
}

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
    this.group.userData.seeThrough = this.status === "planned";
    zone.root.add(this.group);
    zone.parts.push(this);
  }

  add(...objects) {
    this.group.add(...objects);
  }

  /**
   * A material for this part. hue names its biology colour (used with "Colour: Biology");
   * shade lightens (+) or darkens (-). A planned part is a sketch whatever is asked for:
   * thin outlines (line) or a wire mesh (wire). rim and alphaRim give solid parts a soft lit edge.
   */
  material({ hue = null, opacity = 1, wire = false, line = false, shade = 0, emissive = 0, roughness = 0.42, flat = false, side = THREE.FrontSide, clip = false, depthWrite, rim = 0.3, alphaRim = 0 } = {}) {
    const sketch = wire || line || this.status === "planned";
    let material;
    if (sketch) {
      material = new THREE.MeshBasicMaterial({ wireframe: !line, transparent: true, opacity: line ? 0.9 : 0.6, depthWrite: false });
      opacity = material.opacity;
    } else {
      if (this.status === "designed") opacity *= 0.45;
      material = new THREE.MeshStandardMaterial({ roughness, metalness: 0, flatShading: flat, side, transparent: opacity < 1, opacity, depthWrite: depthWrite ?? opacity === 1 });
      soften(material, { rim, alphaRim });
    }
    if (clip) material.clippingPlanes = CUT_PLANES;
    return this.register(material, { base: opacity, hue, shade, emissive, sketch });
  }

  /** Dots, for what is too small to draw as shapes. size is in screen pixels. */
  points({ hue = null, shade = 0, size = 1.6, opacity = 0.9 } = {}) {
    const material = new THREE.PointsMaterial({ size, sizeAttenuation: false, map: dotTexture(), alphaTest: 0.35, transparent: true, opacity, depthWrite: false });
    return this.register(material, { base: opacity, hue, shade, emissive: 0, sketch: this.status === "planned", dust: true });
  }

  /** Thin lines: outlines of a planned part, or fine structure of a built one. */
  lineMaterial({ hue = null, opacity = 0.8 } = {}) {
    const material = new THREE.LineBasicMaterial({ transparent: true, opacity, depthWrite: false });
    return this.register(material, { base: opacity, hue, shade: 0, emissive: 0, sketch: this.status === "planned" || !hue });
  }

  /** Draws nothing, but can be clicked: the body of a part that is drawn only as outlines. */
  proxyMaterial() {
    return (Part.proxy ??= new THREE.MeshBasicMaterial({ colorWrite: false, depthWrite: false }));
  }

  register(material, data) {
    material.userData = { ...material.userData, ...data, solidDepth: material.depthWrite };
    this.materials.push(material);
    return material;
  }

  colour(palette) {
    const byBiology = this.lens.colourBy === "biology";
    for (const material of this.materials) {
      const data = material.userData;
      const name = data.sketch ? "ghost" : byBiology && data.hue ? data.hue : statusToken(this.status);
      const colour = new THREE.Color(palette[name] || palette.ghost);
      if (data.shade > 0) colour.lerp(WHITE, data.shade);
      else if (data.shade < 0) colour.lerp(BLACK, -data.shade);
      material.color.copy(colour);
      data.tint = colour;
      // The rim is a lighter tone of the part's own colour, so the colour still reads.
      data.rim?.uRimColor.value.copy(colour).lerp(WHITE, palette.dark ? 0.35 : 0.65);
    }
  }

  /** dim: another part is in focus. hot: this part is under the pointer or selected. */
  look(fade, dim, hot) {
    for (const material of this.materials) {
      const data = material.userData;
      const opacity = data.base * fade * (dim ? 0.14 : 1) * (data.dust ? this.lens.dustFade : 1);
      material.opacity = opacity;
      material.transparent = opacity < 0.999 || data.dust === true;
      material.depthWrite = data.solidDepth && opacity > 0.9;
      if (material.emissive && data.tint) material.emissive.copy(data.tint).multiplyScalar(data.emissive + (hot ? 0.26 : 0));
    }
  }
}

/** Soft surroundings for reflections, so glossy parts have highlights. Belongs to this lens only. */
function makeEnvironment(renderer) {
  try {
    const scene = new THREE.Scene();
    const dome = new THREE.Mesh(new THREE.SphereGeometry(60, 32, 16), new THREE.MeshBasicMaterial({ side: THREE.BackSide, vertexColors: true }));
    const position = dome.geometry.attributes.position, colours = [];
    for (let index = 0; index < position.count; index++) {
      const t = position.getY(index) / 120 + 0.5;
      colours.push(0.32 + 0.7 * t, 0.36 + 0.68 * t, 0.42 + 0.64 * t);
    }
    dome.geometry.setAttribute("color", new THREE.Float32BufferAttribute(colours, 3));
    scene.add(dome);
    for (const [x, y, z, size, power] of [[-22, 34, 26, 30, 3.0], [30, 20, -14, 20, 1.5]]) {
      const panel = new THREE.Mesh(new THREE.PlaneGeometry(size, size), new THREE.MeshBasicMaterial({ color: new THREE.Color(power, power, power), side: THREE.DoubleSide }));
      panel.position.set(x, y, z);
      panel.lookAt(0, 0, 0);
      scene.add(panel);
    }
    const generator = new THREE.PMREMGenerator(renderer);
    const texture = generator.fromScene(scene, 0.035).texture;
    generator.dispose();
    scene.traverse((object) => {
      object.geometry?.dispose();
      object.material?.dispose();
    });
    return texture;
  } catch (error) {
    console.warn("cell lens: no environment map; continuing without reflections", error);
    return null;
  }
}

export class CellLens {
  constructor(stage, model, labels) {
    this.id = "cell";
    this.stage = stage;
    this.model = model;
    this.labels = labels;
    this.root = new THREE.Group();
    this.zones = [];
    this.byEntity = new Map(); // entity id -> [Part]
    this.selected = null;
    this.hovered = null;
    this.isolate = null;
    this.together = null;
    this.colourBy = "biology";
    this.sizeMode = "schematic";
    this.activeStop = "cell";
    this.dustFade = 1;
    this.clock = 0;
    this.active = false;
    this.capabilityByPart = new Map(model.ofKind("capability").map((entity) => [entity.part, entity]));
    this.environment = makeEnvironment(stage.renderer);
    stage.raycaster.params.Points.threshold = 0.06;
    this.build();
    this.applyPalette(stage.palette);
  }

  // ------------------------------------------------------------ building

  zone(name, mode = null) {
    const range = mode ? RANGES[mode][name] : RANGES.shared[name];
    const zone = { name, mode, range, root: new THREE.Group(), parts: [], neutrals: [], labels: [], fade: -1 };
    this.zones.push(zone);
    this.root.add(zone.root);
    return zone;
  }

  context(zone) {
    return {
      part: (name, anchor) => this.bind(this.capabilityByPart.get(name), zone, anchor, name),
      scale: (id, anchor) => this.bind(this.model.get(id), zone, anchor, id),
      neutral: (options = {}) => {
        const material = new THREE.MeshStandardMaterial({ roughness: 0.6, metalness: 0, transparent: true, side: options.side ?? THREE.FrontSide, depthWrite: options.depthWrite ?? false });
        if (options.glass) soften(material, { rim: 0.2, alphaRim: options.glass });
        if (options.clip) material.clippingPlanes = CUT_PLANES;
        return this.neutral(zone, material, options);
      },
      neutralLine: (options = {}) =>
        this.neutral(zone, options.dashed ? new THREE.LineDashedMaterial({ transparent: true, dashSize: 3, gapSize: 2.2 }) : new THREE.LineBasicMaterial({ transparent: true }), options),
      illustrate: (object, zoneName) => {
        object.userData.unpickable = true;
        (zoneName ? this.zones.find((item) => item.name === zoneName) : zone).root.add(object);
      },
      sprite: (part, text, position, size) => {
        const sprite = glyphSprite(text, "#ffffff", size);
        sprite.position.copy(position);
        sprite.userData.unpickable = true;
        this.neutral(part.zone, sprite.material, { opacity: 0.85, colour: "fg" });
        part.add(sprite);
      },
    };
  }

  build() {
    this.fill = new THREE.DirectionalLight(0xffffff, 0.7);
    this.fill.position.set(-70, 25, -40);
    this.root.add(this.fill);
    this.cells = {};
    for (const mode of SIZE_MODES) {
      const cell = this.context(this.zone("cell", mode));
      const studs = this.context(this.zone("studs", mode));
      const handles = buildCell(cell, studs, mode);
      handles.molecule = buildMolecules(this.context(this.zone("molecules", mode)), mode);
      this.cells[mode] = handles;
    }
    this.sheet = buildTissue(this.context(this.zone("tissue")));
    buildOrgan(this.context(this.zone("organ")));
    buildOrganism(this.context(this.zone("organism")));
    this.stops = Object.fromEntries(SIZE_MODES.map((mode) => [mode, this.makeStops(mode)]));
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
    material.userData = { ...material.userData, base: opacity, colour };
    material.opacity = opacity;
    zone.neutrals.push(material);
    return material;
  }

  makeStops(mode) {
    const entity = (id) => this.model.get(id);
    const molecule = this.cells[mode].molecule;
    const out = molecule.outward;
    return [
      { id: "molecule", entity: entity("scale.molecule"), zone: "molecules", anchor: molecule.centre.clone().addScaledVector(out, molecule.view[1] * 0.3), size: molecule.view, target: molecule.centre.clone(), azimuth: molecule.fromInside ? Math.atan2(-out.x, -out.z) : Math.atan2(out.x, out.z), polar: molecule.fromInside ? 0.42 : 0.6 },
      { id: "cell", entity: entity("scale.cell"), zone: "cell", anchor: new THREE.Vector3(0, CUT + 2.6, -RIM - 1.6), size: [42, 31], target: new THREE.Vector3(0.8, CUT - 2.6, 0.2), azimuth: 0.52, polar: 0.84 },
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

  get currentStops() {
    return this.stops[this.sizeMode];
  }

  /** World points the input check clicks; they follow the layout of the current size mode. */
  get probes() {
    return this.cells[this.sizeMode].probes;
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
      rail: this.currentStops.map((stop) => ({ id: stop.id, label: stop.entity?.label || stop.id, title: stop.entity?.plain })),
      railActive: this.activeStop,
      together: (this.model.raw.model_groups || []).map((group) => ({ id: group.id, label: group.label, title: group.description })),
      togetherActive: this.together,
      view: { colour: this.colourBy, size: this.sizeMode },
    };
  }

  /** What the scale bar may say: micrometres per unit, or why no bar applies here. */
  scaleInfo() {
    const distance = this.stage.rig.distance;
    if (this.sizeMode === "schematic" && distance < 13) return { note: "Close-up not to scale" };
    return { micronsPerUnit: 1, note: this.sizeMode === "schematic" && distance < 190 ? "small parts enlarged" : null };
  }

  /** Where callout labels go: the cell's centre and radius on screen, or null to label parts in place. */
  calloutFrame() {
    const zone = this.zones.find((item) => item.name === "cell" && item.mode === this.sizeMode);
    if (!zone || zone.fade < 0.6 || this.stage.width < 900 || this.stage.rig.distance < 34) return null;
    const { camera } = this.stage;
    const centre = new THREE.Vector3(0, CUT - 2.2, 0);
    const span = camera.position.distanceTo(centre) * Math.tan((camera.fov * Math.PI) / 360);
    const screen = this.stage.project(centre, new THREE.Vector3());
    return { x: screen.x, y: screen.y, radius: (R * 1.1 * this.stage.height) / (2 * span) };
  }

  get pickRoots() {
    return [this.root];
  }

  activate() {
    const { stage } = this;
    this.active = true;
    stage.scene.add(this.root);
    stage.sun.castShadow = false;
    stage.sun.position.set(55, 100, 80);
    stage.sun.target.position.set(0, 0, 0);
    stage.rig.limits = { minDistance: 0.03, maxDistance: 130000, minPolar: 0.1, maxPolar: 2.35 };
    this.light();
    stage.rig.setView(this.stopView(this.currentStops.find((stop) => stop.id === this.activeStop)));
    this.buildLabels();
    this.fades(true);
    this.refresh();
  }

  deactivate() {
    this.active = false;
    this.stage.scene.remove(this.root);
    this.stage.scene.environment = null;
    this.stage.applyPalette(); // back to the stage's own lighting
    this.labels.clear();
    this.labels.calloutFrame = null;
  }

  /** This lens's lighting: reflections from its environment, and a little less direct light. */
  light() {
    const { stage } = this;
    const dark = stage.palette.dark;
    stage.scene.environment = this.environment;
    stage.scene.environmentIntensity = dark ? 0.5 : 0.62;
    stage.sky.intensity = dark ? 0.95 : 1.2;
    stage.sun.intensity = dark ? 1.45 : 1.2;
    this.fill.intensity = dark ? 0.9 : 0.6;
  }

  shows(zone) {
    return !zone.mode || zone.mode === this.sizeMode;
  }

  buildLabels() {
    const labels = this.labels;
    labels.clear();
    labels.calloutFrame = () => this.calloutFrame();
    for (const zone of this.zones) zone.labels = [];
    for (const parts of this.byEntity.values()) {
      for (const part of parts) {
        part.label = null;
        if (!part.anchor || !this.shows(part.zone)) continue;
        const isScale = part.entity.kind === "scale";
        const atCell = part.zone.name === "cell" || part.zone.name === "studs";
        part.label = labels.add({
          id: part.entity.id,
          text: part.entity.label,
          anchor: part.anchor,
          priority: isScale ? 300 : this.model.isBuilt(part.entity) ? 40 : 50,
          kind: isScale ? "scale" : "part",
          lift: isScale ? 4 : 9,
          swatch: isScale ? undefined : part.entity.status || "unstated",
          callout: atCell,
        });
        part.zone.labels.push(part.label);
      }
    }
    const zoneOf = (name) => this.zones.find((zone) => zone.name === name && this.shows(zone));
    for (const stop of this.currentStops) {
      if (!stop.anchor || !stop.entity) continue;
      zoneOf(stop.zone).labels.push(labels.add({ id: stop.entity.id, text: stop.entity.label, anchor: stop.anchor, priority: 300, kind: "scale", lift: 4 }));
    }
    const molecule = this.cells[this.sizeMode].molecule;
    const text = this.sizeMode === "real" ? "To scale: the membrane is about 5 nm thick, the channel about 9 nm across" : "Illustration: channels and pumps are modelled as populations";
    zoneOf("molecules").labels.push(labels.add({ text, anchor: molecule.centre.clone().addScaledVector(molecule.outward, -molecule.view[1] * 0.3), priority: 290, kind: "note", lift: 0 }));
  }

  goToScale(id, immediate = false) {
    const stop = this.currentStops.find((item) => item.id === id);
    if (!stop) return;
    const view = this.stopView(stop);
    this.stage.rig.limits.minDistance = 0.03;
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

  /** "biology": each kind of part has its own colour. "status": colour shows status, as in the engine lens. */
  setColourBy(mode) {
    this.colourBy = mode === "status" ? "status" : "biology";
    this.applyPalette(this.stage.palette);
    this.onChrome?.();
  }

  setSizeMode(mode) {
    if (!SIZE_MODES.includes(mode) || mode === this.sizeMode) return;
    const atMolecule = this.activeStop === "molecule";
    this.sizeMode = mode;
    if (this.active) {
      this.buildLabels();
      // The close-up differs by a factor of about a hundred between the modes: go to the new one.
      if (atMolecule) this.goToScale("molecule");
    }
    this.fades(true);
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
      const lit = this.lit(parts[0].entity);
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
      const stop = this.currentStops.find((item) => item.entity?.id === id);
      if (stop) this.goToScale(stop.id);
      return;
    }
    const parts = (this.byEntity.get(id) || []).filter((part) => this.shows(part.zone));
    const part = parts.find((item) => item.anchor) || parts[0];
    if (!part) return;
    const zoneName = part.zone.name === "studs" || part.zone.name === "molecules" ? "cell" : part.zone.name;
    const view = this.stopView(this.currentStops.find((item) => item.zone === zoneName));
    if (zoneName === "cell" && part.anchor) {
      view.target = view.target.clone().lerp(part.anchor, 0.35);
      view.distance *= 0.86;
    }
    this.stage.rig.flyTo(view, 1300);
  }

  // ------------------------------------------------------------ fading between scales

  fades(force = false) {
    const rig = this.stage.rig;
    const distance = rig.distance;
    let changed = false;
    const dust = this.sizeMode === "real" ? smooth(0.5, 1.6, distance) : 1;
    if (Math.abs(dust - this.dustFade) > 0.004) {
      this.dustFade = dust;
      force = true;
    }
    for (const zone of this.zones) {
      const range = zone.range;
      const fade = !this.shows(zone) ? 0 : (range.in ? smooth(range.in[0], range.in[1], distance) : 1) * (range.out ? 1 - smooth(range.out[0], range.out[1], distance) : 1);
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
    for (const stop of this.currentStops) {
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
    // The camera may come close at the cut edge, but looking at the middle of the cell it stays outside.
    const atEdge = smooth(RIM * 0.72, RIM * 0.97, Math.hypot(rig.target.x, rig.target.z));
    rig.limits.minDistance = R + 6 + (0.03 - R - 6) * atEdge;
    return changed;
  }

  update(dt) {
    const changed = this.fades();
    const near = this.zones.some((zone) => zone.mode === this.sizeMode && zone.fade > 0.02);
    if (!near) return changed;
    if (this.stage.reducedMotion) {
      this.animate(0.35);
      return changed;
    }
    this.clock += dt / 1000;
    this.animate(this.clock);
    return true;
  }

  /** Small motions that say what a part does: water crossing, signals leaving, ions through a channel. */
  animate(time) {
    const cell = this.cells[this.sizeMode];
    for (const stream of cell.streams) {
      stream.drops.forEach((drop, index) => {
        const t = (time * 0.2 + index / stream.drops.length) % 1;
        const offset = stream.inward ? stream.reach - t * stream.reach * 1.9 : -stream.reach * 0.9 + t * stream.reach * 1.9;
        drop.position.set(Math.cos(stream.angle) * (RIM + offset), CUT + 0.28, Math.sin(stream.angle) * (RIM + offset));
        drop.scale.setScalar(0.55 + 0.45 * Math.sin(Math.PI * t));
      });
    }
    cell.signals.forEach((bead, index) => {
      const t = (time * 0.08 + index / cell.signals.length) % 1;
      bead.position.copy(cell.signalPath(t));
      bead.scale.setScalar(0.5 + 0.7 * Math.sin(Math.PI * Math.min(1, t * 1.15)));
    });
    cell.cages.forEach((cage, index) => cage.rotation.set(time * 0.22 + index, time * 0.35 + index * 2, 0));
    cell.molecule.ions.forEach((ion, index) => {
      const t = (time * 0.3 + index / cell.molecule.ions.length) % 1;
      ion.position.copy(cell.molecule.ionPath(t));
    });
  }

  applyPalette(palette) {
    for (const zone of this.zones) {
      for (const part of zone.parts) part.colour(palette);
      for (const material of zone.neutrals) {
        material.color.set(palette[material.userData.colour] || palette.ghost);
        material.userData.rim?.uRimColor.value.copy(material.color).lerp(WHITE, 0.5);
      }
    }
    if (this.active) this.light();
    this.refresh();
    this.fades(true);
  }

  dispose() {
    disposeTree(this.root);
    this.environment?.dispose();
  }
}
