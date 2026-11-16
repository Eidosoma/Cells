// An assembly's lineage: the view of a model system under "Origin of life" (schema/ASSEMBLY_RUN.md;
// docs/ORIGIN_OF_LIFE.md, "Decided"). Its levels are the entry's: the molecules (the table of
// catalysis the assembly grows by), one assembly (a bead for each molecule, growing and splitting,
// with its composition round it), a population (its place is left; no run of one exists) and the
// lineage (the tape of compositions, the similarity at each fission with the analysis's threshold,
// the carpet, the spine of daughters, the map of compositions). Everything follows one clock: the
// page's timeline, counting fissions.
//
// The view names no model: the run file does. It reads the run's H and the analysis's marks and
// decides none; it names a composome only where the analysis names one; every choice of the
// picture is said to be the picture's. An example run keeps its mark on the picture while shown.

import * as THREE from "../three.js";
import { roundedSlab } from "../core/materials.js";
import { makeEnvironment, makeStudio } from "../core/environment.js";
import { disposeTree } from "../core/stage.js";
import { Player } from "../replay/player.js";
import { AssemblySet, PREFIX } from "./assembly_run.js";
import { BeadLayout, BeadMeshes, arrivalMode, SHAPES } from "./assembly_beads.js";
import { CompositionRing, CompositionStrip, CompositionTape } from "./composition_marks.js";
import { SimilarityFence, SimilarityCarpet, COMPARE } from "./similarity_marks.js";
import { LineageSpine, CompositionMap } from "./lineage_marks.js";
import { CatalysisTable } from "./catalysis_table.js";
import { clockOf, fissionsPerSecond, FINE } from "./lineage_clock.js";
import { describe as describePart, sections as listSections } from "./lineage_card.js";

/** The look this view asks of the stage: studio light on the beads, contact shade where parts meet the plate. */
export const ORIGIN_LOOK = { rich: true, filmic: true, exposure: 1.05, contact: true, reach: 0.5, shade: 0.5 };

/** The levels an entry may give this view, in order; an entry names which it has (schema, "What the lens needs from an entry"). */
export const LEVELS = [
  { id: "molecules", label: "Molecules" },
  { id: "assembly", label: "One assembly" },
  { id: "population", label: "Population", waiting: "Not drawn yet: a population needs a run of several slots, and no run of one exists." },
  { id: "lineage", label: "Lineages" },
];
export const COMPOSITION = [["wheel", "Wheel"], ["strip", "Strip"]];

const ASSEMBLY = new THREE.Vector3(0, 1.85, 0);
const TAPE_Y = 6.1; // the tape's middle, above the fence's tallest post
const SPAN = 22; // the lineage's length along the scene, whatever its number of fissions
const TOKENS = {
  lead: ["--origin-type-1", "--origin-type-2", "--origin-type-3"],
  other: "--origin-type-other", otherAlt: "--origin-type-other-2", tail: "--origin-tail", glow: "--origin-glow",
  ramp: ["--origin-ramp-0", "--origin-ramp-1", "--origin-ramp-2", "--origin-ramp-3", "--origin-ramp-4", "--origin-ramp-5"],
};

/** The view's own colours, from its tokens (src/ui/origin_styles.js); where they are absent, the page's neutral ones. */
export function readTokens(host, palette = {}) {
  const style = host && typeof getComputedStyle === "function" ? getComputedStyle(host) : null;
  const read = (name, fallback) => (style ? style.getPropertyValue(name).trim() : "") || fallback || "#888888";
  const seq = [palette.seq0, palette.seq1, palette.seq2, palette.seq3, palette.seq4, palette.seq4];
  return {
    lead: TOKENS.lead.map((name, slot) => read(name, [palette.accent, palette.edge, palette.ghost][slot])),
    other: read(TOKENS.other, palette.ghost), otherAlt: read(TOKENS.otherAlt, palette.plateEdge),
    tail: read(TOKENS.tail, palette.edge), glow: read(TOKENS.glow, palette.accent),
    ramp: TOKENS.ramp.map((name, index) => read(name, seq[index])),
    fromTokens: Boolean(style && style.getPropertyValue(TOKENS.lead[0]).trim()),
  };
}

export class LineageLens {
  constructor(stage, model, labels, file = model?.raw?.assembly_run, { entry = null } = {}) {
    this.id = "origin";
    this.stage = stage;
    this.model = model;
    this.labels = labels;
    this.set = file instanceof AssemblySet ? file : new AssemblySet(file);
    if (entry?.id && entry.id !== this.set.model.id) throw new Error(`the run is of the model ${this.set.model.id}, not of the entry ${entry.id}`);
    this.entry = entry;
    this.runs = this.set.runs;
    this.mainRun = this.runs[0];
    this.mainEnvironment = this.mainRun.environment;
    this.leading = this.mainRun.leading(3);
    this.pair = false;
    this.level = "assembly";
    this.compare = "carried";
    this.composition = "wheel";
    this.narrow = false;
    this.shape = stage.reducedMotion ? "cluster" : "micelle";
    this.selected = null;
    this.hovered = null;
    this.active = false;
    this.player = new Player();
    this.root = new THREE.Group();
    this.materials = this.makeMaterials();
    this.build();
    this.applyPalette(stage.palette || {});
  }

  get shownRuns() {
    return this.pair && this.runs.length > 1 ? this.runs.slice(0, 2) : [this.mainRun];
  }

  runById(id) {
    return this.runs.find((run) => run.id === id) || null;
  }

  // ------------------------------------------------------------ materials

  makeMaterials() {
    const standard = (options) => new THREE.MeshStandardMaterial({ roughness: 0.5, metalness: 0.04, ...options });
    const basic = (options) => new THREE.MeshBasicMaterial({ toneMapped: false, ...options });
    const line = (options) => new THREE.LineBasicMaterial({ toneMapped: false, ...options });
    // A type's colour carries its identity: it stays out of filmic light (toneMapped false), as the Laws view's chosen marks do.
    const materials = {
      lead: standard({ roughness: 0.38, toneMapped: false, envMapIntensity: 0.55 }),
      other: standard({ roughness: 0.6, toneMapped: false, envMapIntensity: 0.4 }),
      tail: line({ vertexColors: true, transparent: true, opacity: 0.7 }),
      glow: basic({ transparent: true, opacity: 0.32, depthWrite: false }),
      ring: basic({ vertexColors: true, side: THREE.DoubleSide }),
      strip: standard({ roughness: 0.45, toneMapped: false }),
      plate: standard({ roughness: 0.85 }),
      post: standard({ roughness: 0.4 }),
      cap: standard({ roughness: 0.35, toneMapped: false }),
      sheet: new THREE.MeshPhysicalMaterial({ roughness: 0.12, metalness: 0, transparent: true, opacity: 0.22, clearcoat: 1, depthWrite: false, side: THREE.DoubleSide }),
      cursor: line({ transparent: true, opacity: 0.8 }),
      node: standard({ roughness: 0.35, toneMapped: false }),
      stub: basic({ transparent: true, opacity: 0.35 }),
      spine: line({}),
      spineThin: new THREE.LineDashedMaterial({ dashSize: 0.08, gapSize: 0.06, toneMapped: false }),
      stem: line({ transparent: true, opacity: 0.45 }),
      point: standard({ roughness: 0.4, toneMapped: false }),
      trail: line({ transparent: true, opacity: 0.7 }),
      trailDashed: new THREE.LineDashedMaterial({ dashSize: 0.05, gapSize: 0.04, toneMapped: false }),
      frame: line({ transparent: true, opacity: 0.28 }),
      now: basic({}),
      composome: basic({ transparent: true, opacity: 0.8 }),
      column: standard({ roughness: 0.45, toneMapped: false }),
      slot: new THREE.MeshPhysicalMaterial({ roughness: 0.15, transparent: true, opacity: 0.18, depthWrite: false }),
      arrows: [0, 1, 2].map(() => line({})),
      arrowHeads: [0, 1, 2].map(() => basic({})),
      leading: [0, 1, 2].map(() => standard({ roughness: 0.4, toneMapped: false })),
    };
    for (const name of ["glow", "ring", "cursor", "spine", "spineThin", "stem", "trail", "trailDashed", "frame", "now", "composome", "stub", "tail"]) materials[name].userData.noContact = true;
    return materials;
  }

  // ------------------------------------------------------------ the picture

  /** Where each place stands, wide or narrow. */
  places() {
    const narrow = this.narrow;
    return {
      table: narrow ? [-9, 0, 9] : [-21, 0, -2],
      population: narrow ? [9, 0, 9] : [21, 0, -2],
      lineage: { z: -6, x0: -SPAN / 2, x1: SPAN / 2 },
      carpet: narrow ? [-3.2, 0.03, 4.4] : [-8, 0.03, -2.4],
      map: narrow ? [3.4, 2.3, 4.4] : [8, 2.4, -2.4],
    };
  }

  build() {
    this.root.traverse((object) => object.geometry?.dispose?.());
    for (const child of [...this.root.children]) this.root.remove(child);
    const places = this.places();
    this.placeAt = places;
    // The plate everything stands on.
    const plate = new THREE.Mesh(roundedSlab(this.narrow ? 28 : 56, this.narrow ? 36 : 22, 1.4, 0.05), this.materials.plate);
    plate.scale.y = 0.3;
    plate.position.set(0, -0.32, this.narrow ? 0 : -3);
    plate.receiveShadow = true;
    plate.userData.unpickable = true;
    this.root.add(plate);
    // A group for each place, shown by level: the lineage's parts stand in theirs.
    this.lineageGroup = new THREE.Group();
    this.root.add(this.lineageGroup);
    // One side for each run shown: its assembly, its composition, its lineage.
    const runs = this.shownRuns;
    const xOfRun = (run) => (k) => places.lineage.x0 + (k / run.fissionCount) * (places.lineage.x1 - places.lineage.x0);
    this.sides = runs.map((run, index) => {
      const group = new THREE.Group();
      const offset = runs.length > 1 ? (index === 0 ? -2.7 : 2.7) : 0;
      group.position.set(ASSEMBLY.x + offset, ASSEMBLY.y, ASSEMBLY.z);
      this.root.add(group);
      const layout = new BeadLayout({ seed: 2026 + index });
      layout.shape = this.shape;
      layout.axis = this.narrow ? 1 : 0;
      const meshes = new BeadMeshes(group, this.materials);
      for (const mesh of meshes.meshes) mesh.userData.pick = (hit) => { const bead = meshes.beadOf(hit); return bead ? `${PREFIX}type:${bead.type}` : `${PREFIX}assembly`; };
      const ring = new CompositionRing(group, this.materials.ring);
      const strip = new CompositionStrip(group, this.materials.strip);
      const z = places.lineage.z + index * 1.6;
      const xOf = xOfRun(run);
      const fence = new SimilarityFence(this.lineageGroup, run, { xOf, z: z - 0.45, y: 0.95, materials: this.materials });
      const spine = new LineageSpine(this.lineageGroup, run, { xOf, y: 0.42, z: z + 0.4, materials: this.materials });
      return { run, group, layout, meshes, ring, strip, fence, spine, xOf, offset };
    });
    // The lineage's wall, carpet and map: of the first run.
    const main = this.sides[0];
    // The tape stands above the fence's posts, so that neither hides the other.
    this.tape = new CompositionTape(this.lineageGroup, this.mainRun, { width: SPAN, height: 3.4, at: [0, TAPE_Y, places.lineage.z - 2.6] });
    this.carpet = new SimilarityCarpet(this.lineageGroup, this.mainRun, { size: this.narrow ? 5.5 : 4.6, at: places.carpet, materials: this.materials });
    this.map = new CompositionMap(this.lineageGroup, this.mainRun, { centre: places.map, size: this.narrow ? 1.5 : 1.6, materials: this.materials, leading: this.leading });
    this.table = new CatalysisTable(this.root, this.mainEnvironment, { size: this.narrow ? 7 : 9, centre: places.table, materials: this.materials, leading: this.leading });
    // The population's place: empty glass slots, waiting for a run of one.
    this.population = new THREE.Group();
    this.population.position.set(...places.population);
    const slots = new THREE.InstancedMesh(new THREE.CylinderGeometry(0.42, 0.42, 0.12, 24), this.materials.slot, 24);
    const dummy = new THREE.Object3D();
    for (let s = 0; s < 24; s++) {
      const a = (s / 24) * Math.PI * 2;
      dummy.position.set(Math.cos(a) * 3, 0.1, Math.sin(a) * 3);
      dummy.updateMatrix();
      slots.setMatrixAt(s, dummy.matrix);
    }
    slots.userData.pick = `${PREFIX}part:population`;
    this.population.add(slots);
    this.root.add(this.population);
    this.main = main;
    this.keys = {};
    this.showLevel();
  }

  /** Each level shows its own place; the assembly stays in front of its lineage. */
  showLevel() {
    const level = this.level;
    for (const side of this.sides) side.group.visible = level === "assembly" || level === "lineage";
    this.lineageGroup.visible = level === "lineage";
    this.table.group.visible = level === "molecules";
    this.population.visible = level === "population";
  }

  // ------------------------------------------------------------ the lens interface

  has(id) {
    return Boolean(id && id.startsWith(PREFIX) && this.describe(id));
  }

  describe(id) {
    return describePart(this, id);
  }

  sections() {
    return listSections(this);
  }

  entities() {
    return this.sections().flatMap((section) => section.entities);
  }

  get pickRoots() {
    return [this.root];
  }

  /** The panel's sources: files of the repository, as every view gives them (the papers are named in words, in the facts). */
  sourcesOf() {
    return [{ path: "schema/ASSEMBLY_RUN.md", where: "what the view reads of a run" }, ...(this.set.example ? [{ path: "data/origin/example-run.json", where: "the example, written by tools/make_assembly_example.mjs" }] : [])];
  }

  /** The papers a run's rules rest on, in words: each with its DOI and licence. */
  papers() {
    return Object.values(this.set.file.sources || {}).map((source) => `${source.text}${source.doi ? ` doi:${source.doi}` : ""} (${source.licence}): ${source.for}`).join("; ");
  }

  /** The levels this view offers: the entry's where it gives them, else all four. */
  levels() {
    const ids = this.entry?.levels?.map((level) => level.id) || LEVELS.map((level) => level.id);
    return LEVELS.filter((level) => ids.includes(level.id)).map((level) => ({ ...level, label: this.entry?.levels?.find((item) => item.id === level.id)?.label || level.label, active: level.id === this.level }));
  }

  setLevel(id) {
    if (!LEVELS.some((level) => level.id === id) || !this.levels().some((level) => level.id === id)) return false;
    this.level = id;
    this.showLevel();
    if (this.active) this.stage.rig?.flyTo?.(this.homeView());
    this.refreshLabels();
    this.stage.invalidate?.();
    this.onChrome?.();
    return true;
  }

  chrome() {
    const example = this.set.example?.says || null;
    return {
      card: {
        heading: this.set.model.label,
        modes: { label: "Shape (the picture's choice)", options: SHAPES.map((shape) => [shape, shape === "micelle" ? "Micelle" : "Cluster"]), active: this.shape },
        marks: { label: "Composition", options: COMPOSITION, active: this.composition },
        compare: { label: "Similarity", options: COMPARE.map((item) => [item.id, item.label]), active: this.compare },
        pair: this.runs.length > 1 ? { label: "Runs under one clock", options: [["one", this.mainRun.label], ["pair", `${this.runs[0].label} and ${this.runs[1].label}`]], active: this.pair ? "pair" : "one" } : null,
        text: [example, this.set.model.plain, this.entry?.modelled?.text || "Nothing of this model is in Cells' engine."].filter(Boolean).join(" "),
        sources: this.sourcesOf(),
      },
      legend: {
        title: "Molecule types",
        example,
        items: [
          ...this.leading.map((type, slot) => ({ id: `${PREFIX}type:${type}`, label: `${this.mainEnvironment.types[type]}, ${["diamond", "cube", "tetrahedron"][slot]}`, swatch: `origin-type-${slot + 1}` })),
          { label: `the other ${this.mainEnvironment.count - this.leading.length} types, spheres`, swatch: "origin-type-other" },
          ...(this.mainRun.threshold ? [{ label: `${this.mainRun.threshold.value}: the analysis's threshold, on the parent with the daughter that carries on`, swatch: "origin-threshold" }] : []),
          { label: "bead: inherited · ring: a break (the analysis's marks)", swatch: "origin-fission" },
        ],
      },
      stamp: [example, this.shownRuns.map((run) => `${run.label}: ${run.law.name}`).join(" · ")].filter(Boolean).join(" · "),
    };
  }

  activate() {
    const { stage } = this;
    this.active = true;
    stage.scene.add(this.root);
    if (stage.sun) {
      stage.sun.castShadow = false;
      stage.sun.position.set(-8, 30, 18);
      stage.sun.target?.position.set(0, 0, -3);
    }
    stage.dress?.(ORIGIN_LOOK);
    this.light();
    this.stopLook ??= stage.look?.onChange?.(() => this.active && this.light());
    if (stage.rig) {
      stage.rig.limits = { minDistance: 2.5, maxDistance: 120, minPolar: 0.2, maxPolar: Math.PI / 2 - 0.02 };
      stage.rig.setView(this.homeView());
    }
    if (this.player.run === null || !this.clock) this.loadClock();
    this.buildLabels();
    this.sync(0);
  }

  /** Point the page's one clock at the runs shown. */
  loadClock() {
    const time = this.player.time;
    this.clock = clockOf(this.set, this.shownRuns);
    this.player.load(this.clock);
    if (time) this.player.seek(time);
  }

  light() {
    const { stage } = this;
    if (!stage.renderer || !stage.scene) return;
    const studio = stage.look?.on?.("reflections") ? (this.studio ??= makeStudio(stage.renderer)) : null;
    this.environment ??= makeEnvironment(stage.renderer);
    stage.scene.environment = studio || this.environment;
    stage.scene.environmentIntensity = stage.palette?.dark ? 0.7 : 0.85;
  }

  deactivate() {
    const { stage } = this;
    this.active = false;
    this.player.pause();
    stage.dress?.({ rich: false });
    stage.scene.remove(this.root);
    if (stage.scene) stage.scene.environment = null;
    stage.applyPalette?.();
    this.labels.clear();
  }

  /** The camera's stop for the level shown. */
  homeView() {
    const places = this.placeAt;
    const far = this.narrow ? 1.75 : 1;
    switch (this.level) {
      case "molecules": return { target: new THREE.Vector3(...places.table), distance: (this.narrow ? 11 : 15) * (this.narrow ? 1.2 : 1), azimuth: 0, polar: 0.72 };
      case "population": return { target: new THREE.Vector3(places.population[0], 0.6, places.population[2]), distance: 11 * far, azimuth: 0.2, polar: 1.05 };
      case "lineage": return this.narrow
        ? { target: new THREE.Vector3(0, 2.6, -2.5), distance: 31, azimuth: 1.05, polar: 1.18 }
        : { target: new THREE.Vector3(0, 3.1, -4.8), distance: 30, azimuth: 0.1, polar: 1.2 };
      default: return { target: ASSEMBLY.clone(), distance: (this.pair ? 11 : 7.5) * (this.narrow ? 1.3 : 1), azimuth: 0.32, polar: 1.3 };
    }
  }

  fitScreen() {
    const narrow = this.stage.width < this.stage.height * 0.9;
    if (narrow === this.narrow) return false;
    this.narrow = narrow;
    if (narrow && !this.chosenShape) this.setShape("cluster", { chosen: false });
    this.rebuild();
    return true;
  }

  rebuild() {
    const at = this.player.time;
    this.build();
    this.applyPalette(this.stage.palette || {});
    if (this.active) {
      this.stage.rig?.setView(this.homeView());
      this.buildLabels();
      this.player.seek(at);
      this.sync(0);
    }
  }

  // ------------------------------------------------------------ choices

  setShape(shape, { chosen = true } = {}) {
    if (!SHAPES.includes(shape)) return;
    if (chosen) this.chosenShape = true;
    this.shape = shape;
    for (const side of this.sides || []) { side.layout.shape = shape; side.layout.at = null; }
    this.keys = {};
    this.refreshLabels();
    this.stage.invalidate?.();
    this.onChrome?.();
  }

  /** The card's first choice: the shape (the picture's). */
  setMode(value) { this.setShape(value); }
  /** The card's second choice: the composition's form round the assembly. */
  setMark(value) {
    if (!COMPOSITION.some(([id]) => id === value)) return;
    this.composition = value;
    this.keys = {};
    this.stage.invalidate?.();
    this.onChrome?.();
  }

  setCompare(value) {
    if (!COMPARE.some((item) => item.id === value)) return;
    this.compare = value;
    this.keys = {};
    this.refreshLabels();
    this.stage.invalidate?.();
    this.onChrome?.();
  }

  /** Show two runs under one clock, each labelled with its law (the user's answer 9), or one. */
  setPair(on) {
    const next = Boolean(on) && this.runs.length > 1;
    if (next === this.pair) return;
    this.pair = next;
    this.rebuild();
    this.loadClock();
    if (this.active) this.buildLabels();
    this.onChrome?.();
  }

  setSelection(id) {
    const next = id && this.has(id) ? id : null;
    this.selected = next;
    // Choosing a fission takes the clock there: the picture then shows that fission.
    const fission = next && next.match(/^assembly:fission:([^:]+):(\d+)$/);
    if (fission) {
      this.player.pause();
      this.player.seek(Number(fission[2]));
    }
    this.keys = {};
    this.stage.invalidate?.();
  }

  setHover(id) {
    this.hovered = id && this.has(id) ? id : null;
  }

  setIsolate() {}

  /** The arrow keys: a fission on or back, by the clock. */
  step(direction = 1) {
    this.player.pause();
    this.player.step(direction > 0 ? 1 : -1);
    this.stage.invalidate?.();
    const k = Math.round(this.player.time);
    return k >= 1 ? `${PREFIX}fission:${this.mainRun.id}:${Math.min(k, this.mainRun.fissionCount)}` : null;
  }

  focus(id) {
    const fission = id && id.match(/^assembly:fission:([^:]+):(\d+)$/);
    if (fission && this.level !== "lineage" && this.level !== "assembly") this.setLevel("assembly");
  }

  // ------------------------------------------------------------ labels

  buildLabels() {
    const labels = this.labels;
    labels.clear();
    this.tags = {};
    if (!this.active) return;
    const places = this.placeAt, level = this.level, z = places.lineage.z;
    const add = (spec) => labels.add({ kind: "part", lift: 0, priority: 300, ...spec });
    const example = this.set.example?.says;
    if (example) {
      // An example keeps its mark on the picture at the place shown.
      const anchor = {
        assembly: ASSEMBLY.clone().add(new THREE.Vector3(0, this.narrow ? -1.95 : this.pair ? 2.3 : 1.6, 0)),
        lineage: new THREE.Vector3(0, TAPE_Y + 2.2, z - 2.6),
        molecules: new THREE.Vector3(places.table[0], 3.2, places.table[2]),
        population: new THREE.Vector3(places.population[0], 2.2, places.population[2]),
      }[level];
      this.tags.example = labels.add({ text: example, anchor, priority: 980, kind: "note label-region label-example", lift: 10 });
      this.tags.example.boost = 1000;
    }
    if (level === "assembly" || level === "lineage") {
      this.tags.shape = add({ id: `${PREFIX}assembly`, text: this.shapeWords(), anchor: ASSEMBLY.clone().add(new THREE.Vector3(0, this.pair || this.narrow ? -2.9 : -2.35, 0)), priority: 520 });
      // Each run of a pair is labelled with its own law, beneath its assembly.
      if (this.pair) for (const side of this.sides) add({ text: `${side.run.label}: ${side.run.law.name}`, anchor: ASSEMBLY.clone().add(new THREE.Vector3(side.offset, -2.05, 0)), priority: 760 });
    }
    if (level === "assembly") {
      this.tags.carries = add({ text: "carries on", anchor: new THREE.Vector3(), priority: 900, lift: 6 });
      this.tags.other = add({ text: "not followed", anchor: new THREE.Vector3(), priority: 880, lift: 6 });
      this.tags.carries.hidden = this.tags.other.hidden = true;
    }
    if (level === "lineage") {
      add({ id: `${PREFIX}part:tape`, text: "The tape: each fission's parent, types down from t000", anchor: new THREE.Vector3(places.lineage.x0 + 3.2, TAPE_Y + 1.95, z - 2.6), priority: 420 });
      add({ id: `${PREFIX}part:fence`, text: "Similarity at each fission: the run's own H", anchor: new THREE.Vector3(places.lineage.x0 + 3, 4.3, z - 0.45), priority: 430 });
      const threshold = this.mainRun.threshold;
      if (threshold) this.tags.sheet = add({ id: `${PREFIX}threshold`, text: `${threshold.value}: the analysis's threshold of inheritance`, anchor: new THREE.Vector3(places.lineage.x1 - 1.5, 0.95 + ((threshold.value - 0.6) / 0.4) * 3.2, z - 0.45), priority: 440 });
      add({ id: `${PREFIX}part:spine`, text: "The lineage: the daughters that carry on", anchor: new THREE.Vector3(places.lineage.x0 + 2.5, 0.1, z + 0.9), priority: 360 });
      add({ id: `${PREFIX}part:carpet`, text: "The carpet: H of every two grown assemblies, worked out by the view", anchor: new THREE.Vector3(places.carpet[0], 0.2, places.carpet[2] + (this.narrow ? 2.9 : 2.5)), priority: 410 });
      add({ id: `${PREFIX}part:map`, text: "The map: axes worked out by the view, the picture's choice", anchor: new THREE.Vector3(places.map[0], places.map[1] + 2.1, places.map[2]), priority: 400 });
      for (const { tip, type } of this.map.arrows) add({ id: `${PREFIX}type:${type}`, text: this.mainEnvironment.types[type], anchor: tip.clone().add(this.map.group.position), priority: 350, lift: 4 });
      for (const { name, centre } of this.map.composomes) add({ id: `${PREFIX}composome:${this.mainRun.id}:${name.id}`, text: `${name.label || name.id}: named by the run's analysis`, anchor: centre.clone().add(this.map.group.position), priority: 600 });
    }
    if (level === "molecules") {
      add({ id: `${PREFIX}part:table`, text: "Catalysis: type j (across) speeds type i (down), log scale", anchor: new THREE.Vector3(places.table[0], 0.4, places.table[2] + (this.narrow ? 4.2 : 5.2)), priority: 410 });
      this.leading.forEach((type, slot) => {
        const mark = this.table.markAt[slot];
        if (mark) add({ id: `${PREFIX}type:${type}`, text: this.mainEnvironment.types[type], anchor: mark.row.clone().add(new THREE.Vector3(-0.3, 0.3, 0)), priority: 330, lift: 2 });
      });
    }
    if (level === "population") add({ id: `${PREFIX}part:population`, text: "Population: not drawn yet. No run of a population exists", anchor: new THREE.Vector3(places.population[0], 1.2, places.population[2]), priority: 410 });
  }

  shapeWords() {
    return this.shape === "micelle" ? "A micelle, heads out: the shape is the picture's choice" : "A loose cluster: the shape is the picture's choice";
  }

  compareWords() {
    const item = COMPARE.find((entry) => entry.id === this.compare);
    return `Similarity at each fission: ${item.says}`;
  }

  refreshLabels() {
    if (!this.active || !this.tags) return;
    this.buildLabels();
  }

  // ------------------------------------------------------------ following the clock

  /** The composition the clock shows for a run (during a split, the parent). */
  compositionNow(run = this.mainRun) {
    return run.compositionAt(this.player.time);
  }

  /** Bring every part to the clock. Returns whether anything still moves. */
  sync(seconds) {
    const still = Boolean(this.stage.reducedMotion);
    const speed = this.player.speed, fine = speed === FINE;
    const mode = arrivalMode({ fine, fissionsPerSecond: fissionsPerSecond(speed), still });
    const time = this.player.time;
    const style = { slotOf: (type) => this.leading.indexOf(type), colours: this.colours };
    let moving = false;
    const chosenType = this.selected?.match(/^assembly:type:(\d+)$/);
    const chosenK = this.selected?.match(/^assembly:fission:[^:]+:(\d+)$/);
    for (const side of this.sides) {
      const { run, layout } = side;
      const phase = run.phaseAt(time);
      layout.mode = mode;
      layout.follow(run, phase);
      moving = layout.step(seconds, { still }) || moving;
      const chosen = chosenType ? layout.beads.find((bead) => bead.type === Number(chosenType[1])) || null : null;
      side.meshes.draw(layout, { slotOf: style.slotOf, colours: this.colours, chosen });
      // The composition round the assembly: two groups during a split.
      const groups = phase.phase === "split"
        ? [{ x: run.carried(phase.k), centre: layout.centres[0], radius: layout.radius(layout.counts[0] || 40), fade: 0 }, { x: run.other(phase.k), centre: layout.centres[1], radius: layout.radius(layout.counts[1] || 40), fade: 0.75 * layout.fade }]
        : [{ x: run.compositionAt(time), centre: [0, 0, 0], radius: layout.radius(layout.counts[0] || 1), fade: 0 }];
      const key = `${phase.phase}:${phase.k}:${phase.e ?? ""}:${phase.phase === "split" ? phase.part.toFixed(3) : ""}:${this.shape}:${this.colours.version}`;
      side.ring.mesh.visible = this.composition === "wheel";
      side.strip.mesh.visible = this.composition === "strip";
      if (this.composition === "wheel") side.ring.draw(groups, style, key);
      else side.strip.draw(groups, style, key);
      const done = Math.min(run.fissionCount, Math.max(0, Math.floor(time + 1e-9)));
      side.fence.draw(done, this.compare, { chosen: chosenK ? Number(chosenK[1]) : null });
      side.spine.draw(done, phase.phase === "grow" ? phase.progress : 0, { chosen: chosenK ? Number(chosenK[1]) : null });
      side.done = done;
      side.phase = phase;
    }
    const main = this.sides[0];
    this.tape.draw(main.done, this.colours.ramp);
    this.carpet.draw(main.done, this.colours.ramp);
    this.map.draw(main.done, this.mainRun.compositionAt(time), this.stage.camera);
    this.table.draw(this.colours.ramp, this.colours);
    this.placeSplitLabels(main);
    this.stage.invalidate?.();
    return moving;
  }

  placeSplitLabels(side) {
    if (!this.tags?.carries) return;
    const splitting = side.phase?.phase === "split" && side.phase.part > 0.2;
    this.tags.carries.hidden = this.tags.other.hidden = !splitting;
    if (!splitting) return;
    const { layout, group } = side;
    // Beneath each daughter, or beside it where the daughters part up and down.
    const below = (centre, count) => (layout.axis === 1
      ? new THREE.Vector3(centre[0] + layout.radius(count || 40) * 1.7 + 0.3, centre[1], centre[2])
      : new THREE.Vector3(centre[0], centre[1] - layout.radius(count || 40) - 0.55, centre[2])).add(group.position);
    this.tags.carries.anchor.copy(below(layout.centres[0], layout.counts[0]));
    this.tags.other.anchor.copy(below(layout.centres[1], layout.counts[1]));
  }

  update(dt = 16, time, real = dt) {
    if (this.stage.width && this.stage.height && this.fitScreen()) return true;
    const playing = this.active ? this.player.tick(real) : false;
    const moving = this.sync(dt / 1000);
    return playing || moving;
  }

  // ------------------------------------------------------------ theme and cost

  applyPalette(palette) {
    this.palette = palette;
    const tokens = readTokens(this.stage.host, palette);
    this.tokens = tokens;
    const tone = (value) => new THREE.Color(value || "#888888");
    const ramp = tokens.ramp.map(tone);
    this.colours = {
      lead: tokens.lead.map(tone), other: tone(tokens.other), otherAlt: tone(tokens.otherAlt), tail: tone(tokens.tail),
      stage: tone(palette.bg), chosen: tone(palette.accent), ramp, version: (this.colours?.version || 0) + 1,
    };
    const set = (name, value) => value && this.materials[name].color.set(value);
    for (const name of ["lead", "other", "strip", "column", "cap", "node", "point"]) this.materials[name].color.set(0xffffff);
    set("plate", palette.plate);
    set("post", palette.ghost);
    set("cap", palette.fg);
    set("node", palette.fg);
    set("stub", palette.ghost);
    set("spine", palette.fg);
    set("spineThin", palette.fg);
    set("stem", palette.ghost);
    set("sheet", palette.accent);
    set("cursor", palette.fg);
    set("point", palette.fg);
    set("trail", palette.muted);
    set("trailDashed", palette.fg);
    set("frame", palette.muted);
    set("now", palette.accent);
    set("composome", palette.accent);
    set("slot", palette.plateEdge);
    set("glow", tokens.glow);
    this.leading.forEach((_, slot) => {
      this.materials.arrows[slot].color.copy(this.colours.lead[slot]);
      this.materials.arrowHeads[slot].color.copy(this.colours.lead[slot]);
      this.materials.leading[slot].color.copy(this.colours.lead[slot]);
    });
    this.materials.cap.color.set(palette.fg || "#888888");
    this.materials.node.color.set(palette.fg || "#888888");
    this.materials.point.color.set(palette.fg || "#888888");
    this.keys = {};
    if (this.tape) { this.tape.shown = -1; this.carpet.shown = -1; this.table.ramp = null; }
    if (this.sides) for (const side of this.sides) { side.ring.key = ""; side.strip.key = ""; side.fence.key = ""; side.spine.key = ""; }
    if (this.active) this.sync(0);
  }

  /** What one frame costs to draw, counted from the scene: draws and triangles of every visible thing. */
  cost() {
    let draws = 0, triangles = 0;
    this.root.traverseVisible((object) => {
      if (!(object.isMesh || object.isLine || object.isPoints)) return;
      const geometry = object.geometry;
      const instances = object.isInstancedMesh ? object.count : 1;
      if (instances === 0) return;
      const range = geometry.drawRange.count === Infinity ? (geometry.index ? geometry.index.count : geometry.attributes.position.count) : geometry.drawRange.count;
      if (range === 0) return;
      draws += 1;
      if (object.isMesh) triangles += (range / 3) * instances;
    });
    return { draws, triangles: Math.round(triangles) };
  }

  dispose() {
    this.stopLook?.();
    disposeTree(this.root);
    this.environment?.dispose?.();
    this.studio?.dispose?.();
  }
}
