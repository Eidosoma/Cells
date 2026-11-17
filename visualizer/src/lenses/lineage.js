// An assembly's lineage: the view of a model system under "Origin of life" (schema/ASSEMBLY_RUN.md;
// docs/ORIGIN_OF_LIFE.md, "Decided"). Its levels are the entry's: the molecules (the table of
// catalysis the assembly grows by), one assembly (a lipid for each molecule, in water, growing and
// splitting, with its composition round it), a population (its place is left; no run of one exists)
// and the lineage (the tape of compositions, the similarity at each fission with the analysis's
// threshold, the carpet, the spine of daughters, the map of compositions). Everything follows one
// clock: the page's timeline, counting fissions.
//
// A scene at the scale of molecules, in water (the user's request of 16 November 2026: "visuall for
// now but maybe law later"). The run gives which type joins or leaves and when, the composition, each
// fission and how it divides the molecules. The picture gives everything else, and says so: how a
// lipid looks, how the lipids move and pack, the water, the free molecules' number and drift, and
// every size. No law of Cells computes how the lipids move and pack.
//
// The view names no model: the run file does. It reads the run's H and the analysis's marks and
// decides none; it names a composome only where the analysis names one; every choice of the
// picture is said to be the picture's. An example run keeps its mark on the picture while shown.

import * as THREE from "../three.js";
import { roundedSlab } from "../core/materials.js";
import { makeEnvironment, makeStudio } from "../core/environment.js";
import { disposeTree } from "../core/stage.js";
import { Player } from "../replay/player.js";
import { AssemblySet, PREFIX, formWords } from "./assembly_run.js";
import { arrivalMode, SHAPES, GLOW_S } from "./assembly_beads.js";
import { LipidLayout, FreeCrowd } from "./lipid_assembly.js";
import { LipidMeshes, lipidMaterials, FORMS } from "./lipid_marks.js";
import { Water, wetten, WATER_THEMES } from "./lipid_water.js";
import { CompositionRing, CompositionStrip, CompositionTape } from "./composition_marks.js";
import { SimilarityFence, SimilarityCarpet, COMPARE } from "./similarity_marks.js";
import { LineageSpine, CompositionMap } from "./lineage_marks.js";
import { CatalysisTable } from "./catalysis_table.js";
import { clockOf, fissionsPerSecond, FINE } from "./lineage_clock.js";
import { describe as describePart, sections as listSections } from "./lineage_card.js";

/** The look this view asks of the stage: studio light on the lipids, and contact shade where the lineage's parts meet the plate. */
export const ORIGIN_LOOK = { rich: true, filmic: true, exposure: 1.05, contact: true, reach: 0.5, shade: 0.5 };
/** Round one assembly the water's own shade (the depth inside the assembly) stands in for contact shade, which would cost a frame more. */
export const ASSEMBLY_LOOK = { ...ORIGIN_LOOK, contact: false };
/**
 * Where the assembly is packed as a loose cluster rather than a micelle by itself: on a phone and with
 * less motion, as the user decided (docs/ORIGIN_OF_LIFE.md, "Decided", answer 2: "a micelle, with the
 * cluster on a phone and where less motion is asked for"). The micelle everywhere (false) was built on
 * the brief of 16 November and has been put to the user; until they say so, their answer stands. The
 * choice is this one line; either packing can be chosen on the card.
 */
export const CLUSTER_WHERE_SMALL_OR_STILL = true;
/** The words the picture says of itself, on the picture and in the legend. */
export const OWN_WORDS = "No law of Cells computes how the lipids move and pack: their look, their motion, the water and every size are the picture's own";
/** The same, in fewer words, for the legend's note, which must stay in view on a short window. */
export const NOTE_WORDS = "No law of Cells computes how the lipids move and pack: that, the water and the halo are the picture's own.";
export const GATHER_WORDS = "The first assembly gathers from the water: the picture's own, since the run starts with it made";

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
const SPAN_NARROW = 9; // on a tall screen, so that the whole lineage is seen from the front at a phone's width
const TOKENS = {
  lead: ["--origin-type-1", "--origin-type-2", "--origin-type-3"],
  other: "--origin-type-other", otherAlt: "--origin-type-other-2", tail: "--origin-tail", glow: "--origin-glow", lipidTail: "--origin-lipid-tail",
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
    tail: read(TOKENS.tail, palette.edge), glow: read(TOKENS.glow, palette.accent), lipidTail: read(TOKENS.lipidTail, palette.dark ? "#b9aa86" : "#e6d9bb"),
    ramp: TOKENS.ramp.map((name, index) => read(name, seq[index])),
    fromTokens: Boolean(style && style.getPropertyValue(TOKENS.lead[0]).trim()),
  };
}

export class LineageLens {
  constructor(stage, model, labels, file = model?.raw?.assembly_run, { entry = null, autoplay = false } = {}) {
    this.id = "origin";
    this.stage = stage;
    this.model = model;
    this.labels = labels;
    this.set = file instanceof AssemblySet ? file : new AssemblySet(file);
    if (entry?.id && entry.id !== this.set.model.id) throw new Error(`the run is of the model ${this.set.model.id}, not of the entry ${entry.id}`);
    this.entry = entry;
    this.runs = this.set.runs;
    // Where two runs are the two forms of the law, the first of them leads (its tape, carpet and map are drawn).
    this.pairRuns = this.set.formsPair();
    this.mainRun = this.pairRuns ? this.pairRuns[0] : this.runs[0];
    this.mainEnvironment = this.mainRun.environment;
    this.leading = this.mainRun.leading(3);
    this.pair = false;
    this.level = "assembly";
    this.compare = "carried";
    this.composition = "wheel";
    this.narrow = false;
    this.autoplay = Boolean(autoplay);
    this.shape = CLUSTER_WHERE_SMALL_OR_STILL && stage.reducedMotion ? "cluster" : "micelle";
    this.selected = null;
    this.hovered = null;
    this.active = false;
    this.player = new Player();
    this.root = new THREE.Group();
    // The water and the free molecules in it: the picture's own (src/lenses/lipid_water.js, lipid_assembly.js).
    this.water = new Water({ narrow: false });
    this.lipid = lipidMaterials(this.water);
    this.crowd = new FreeCrowd(this.mainEnvironment, { narrow: false });
    this.waterTime = 0;
    this.materials = this.makeMaterials();
    this.build();
    this.applyPalette(stage.palette || {});
  }

  get shownRuns() {
    return this.pair && this.pairRuns ? this.pairRuns : [this.mainRun];
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
    // The plate the lineage and the table stand on lies in the water too, with its caustics.
    wetten(materials.plate, this.water, { caustics: 1, rim: 0.06, rimPower: 3 });
    materials.plate.userData.noContact = false;
    return materials;
  }

  // ------------------------------------------------------------ the picture

  /** Where each place stands, wide or narrow. */
  places() {
    const narrow = this.narrow;
    return {
      table: narrow ? [-9, 0, 9] : [-21, 0, -2],
      population: narrow ? [9, 0, 9] : [21, 0, -2],
      // On a tall screen the tape stands lower and less tall, and the carpet and the map close in, so that the whole stack fits under the page's card.
      lineage: narrow ? { z: -6, x0: -SPAN_NARROW / 2, x1: SPAN_NARROW / 2, tapeY: 5.25, tapeHeight: 2.3 } : { z: -6, x0: -SPAN / 2, x1: SPAN / 2, tapeY: TAPE_Y, tapeHeight: 3.4 },
      carpet: narrow ? [-2.3, 0.03, -0.9] : [-8, 0.03, -2.4],
      map: narrow ? [2.5, 1.25, -0.9] : [8, 2.4, -2.4],
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
    this.plate = plate;
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
      const layout = new LipidLayout({ seed: 2026 + index });
      layout.shape = this.shape;
      layout.axis = this.narrow ? 1 : 0;
      const meshes = new LipidMeshes(group, this.lipid, { narrow: this.narrow, capacity: index === 0 ? 420 : 240 });
      for (const mesh of meshes.heads) mesh.userData.pick = (hit) => { const lipid = meshes.lipidOf(hit); return lipid ? `${PREFIX}type:${lipid.type}` : `${PREFIX}assembly`; };
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
    this.tape = new CompositionTape(this.lineageGroup, this.mainRun, { width: places.lineage.x1 - places.lineage.x0, height: places.lineage.tapeHeight, at: [0, places.lineage.tapeY, places.lineage.z - 2.6] });
    this.carpet = new SimilarityCarpet(this.lineageGroup, this.mainRun, { size: this.narrow ? 3.1 : 4.6, at: places.carpet, materials: this.materials });
    this.map = new CompositionMap(this.lineageGroup, this.mainRun, { centre: places.map, size: this.narrow ? 0.9 : 1.6, materials: this.materials, leading: this.leading });
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
    // The marks of the run keep their colours as their legend shows them: the haze is only on what is wet.
    this.root.traverse((object) => {
      for (const material of Array.isArray(object.material) ? object.material : object.material ? [object.material] : []) if (!material.userData.wet) material.fog = false;
    });
    this.water.setNarrow(this.narrow);
    this.crowd.setNarrow(this.narrow);
    this.showLevel();
  }

  /** Each level shows its own place; the assembly stays in front of its lineage. */
  showLevel() {
    const level = this.level;
    // The assembly stands in front of its lineage, but on a phone, where the lineage needs the whole picture.
    for (const side of this.sides) side.group.visible = level === "assembly" || (level === "lineage" && !this.narrow);
    this.lineageGroup.visible = level === "lineage";
    this.table.group.visible = level === "molecules";
    this.population.visible = level === "population";
    // Round one assembly it floats in open water; the other levels stand on the plate.
    this.plate.visible = level !== "assembly";
    this.water.setLevel(level);
    this.water.setCentre(level === "assembly" ? ASSEMBLY : this.homeView().target);
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

  /** On the map's page, the picture keeps clear of the cards on the left (its card and its legend), as the Laws library's does. */
  get wantsLeftRoom() {
    return true;
  }

  /** Its water and free molecules reach the page's top edge, under the bar: the page gives the bar's words a ground there (src/ui/styles.js). */
  get drawsUnderBar() {
    return true;
  }

  /** A card of the page opened or closed (on a phone, the folded card, the rail, the legend): the example's mark finds its place again at the next frame, though nothing moves. */
  cardsMoved() {
    this.exampleSpot = null;
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
    if (this.active) {
      this.stage.dress?.(this.lookFor(id));
      this.limit();
      this.stage.rig?.flyTo?.(this.homeView());
    }
    this.refreshLabels();
    this.stage.invalidate?.();
    this.onChrome?.();
    return true;
  }

  chrome() {
    const example = this.set.example?.says || null;
    const types = this.mainEnvironment.types, others = this.mainEnvironment.count - this.leading.length;
    const lipids = this.level === "assembly" || this.level === "lineage";
    return {
      card: {
        heading: this.set.model.label,
        modes: { label: "Packing (the picture's choice)", options: SHAPES.map((shape) => [shape, shape === "micelle" ? "Micelle" : "Cluster"]), active: this.shape },
        marks: { label: "Composition", options: COMPOSITION, active: this.composition },
        compare: { label: "Similarity", options: COMPARE.map((item) => [item.id, item.label]), active: this.compare },
        pair: this.pairRuns ? { label: "The two forms of the law, under one clock", options: [["one", this.mainRun.label], ["pair", `${this.pairRuns[0].label} and ${this.pairRuns[1].label}`]], active: this.pair ? "pair" : "one" } : null,
        text: [example ? `${example}.` : null, this.set.model.plain, this.entry?.modelled?.text || "Nothing of this model is in Cells' engine."].filter(Boolean).join(" "),
        sources: this.sourcesOf(),
      },
      legend: {
        title: lipids ? "Molecules, as lipids" : "Molecule types",
        example,
        // Each level keys what it draws, in few words, so that the note below stays in view.
        items: [
          // Each key on one line of the legend: a head's colour and form (its panel says more).
          ...this.leading.map((type, slot) => ({ id: `${PREFIX}type:${type}`, label: `${types[type]}: ${["blue", "orange", "green"][slot]} ${FORMS[slot].replace("soft ", "")}`, swatch: `origin-type-${slot + 1}` })),
          { label: `${others} others: round, grey`, swatch: "origin-type-other" },
          ...(this.level === "assembly" ? [
            { label: "tails: alike, turned in", swatch: "origin-tail" },
            { label: "free: the run's supply", swatch: "origin-free" },
            { label: "halo: a molecule in motion", swatch: "origin-halo" },
          ] : []),
          ...(this.level === "lineage" && this.mainRun.threshold ? [{ label: `${this.mainRun.threshold.value}: the analysis's threshold`, swatch: "origin-threshold" }] : []),
          ...(this.level === "lineage" ? [{ label: "bead: inherited · ring: a break", swatch: "origin-fission" }] : []),
        ],
        note: { text: [example ? `${example}.` : null, NOTE_WORDS].filter(Boolean).join(" ") },
      },
      timeline: { player: this.player, eventWord: "fission" },
      stamp: [example, this.shownRuns.map((run) => `${run.label}: ${formWords(run)}`).join(" · ")].filter(Boolean).join(" · "),
    };
  }

  /** What helped a join: shown as a brief light only where the run records it. */
  helpWords() {
    return this.mainRun.raw.trace?.helpers ? null : "No light shows what helped a join: the run does not record it.";
  }

  activate() {
    const { stage } = this;
    this.active = true;
    stage.scene.add(this.root);
    this.water.attach(stage.scene);
    if (stage.sun) {
      stage.sun.castShadow = false;
      stage.sun.position.set(-8, 30, 18);
      stage.sun.target?.position.set(0, 0, -3);
    }
    stage.dress?.(this.lookFor(this.level));
    this.light();
    this.stopLook ??= stage.look?.onChange?.(() => this.active && this.light());
    this.limit();
    stage.rig?.setView(this.homeView());
    if (this.player.run === null || !this.clock) this.loadClock();
    // The page is drawn again whenever the clock moves, playing or not (a scrub of the timeline, a key).
    if (!this.listening) {
      this.listening = () => this.stage.invalidate?.();
      this.player.addEventListener("time", this.listening);
      this.player.addEventListener("state", this.listening);
    }
    this.buildLabels();
    this.sync(0);
    // Back from another view: it plays again if it was playing when the visitor left it.
    if (this.wasPlaying) this.player.play();
    this.wasPlaying = false;
  }

  /**
   * The look a level asks of the stage. Contact shade only where the catalysis table's columns stand on
   * the plate (the Molecules level): at the Lineages level it cost a frame about 1.5 ms on the card and
   * kept the page just under 60 frames a second at 1400 by 900 (17 November 2026), and round one
   * assembly the water's own shade stands in for it.
   */
  lookFor(level) {
    return level === "molecules" ? ORIGIN_LOOK : ASSEMBLY_LOOK;
  }

  /** How the camera may move: all round one assembly in open water; above the plate elsewhere. */
  limit() {
    if (!this.stage.rig) return;
    this.stage.rig.limits = { minDistance: 2.5, maxDistance: 120, minPolar: 0.2, maxPolar: this.level === "assembly" ? Math.PI - 0.35 : Math.PI / 2 - 0.02 };
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
    this.wasPlaying = this.player.playing;
    this.player.pause();
    stage.dress?.({ rich: false });
    stage.scene.remove(this.root);
    this.water.detach(stage.scene);
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
        ? { target: new THREE.Vector3(0, 5.15, -3.4), distance: 28.5, azimuth: 0.12, polar: 1.2 }
        : { target: new THREE.Vector3(0, 3.1, -4.8), distance: 30, azimuth: 0.1, polar: 1.2 };
      default: return { target: ASSEMBLY.clone().add(new THREE.Vector3(this.narrow || this.pair ? 0 : 0.35, this.narrow ? 0.3 : -0.45, 0)), distance: (this.pair ? 12 : 6.6) * (this.narrow ? 1.3 : 1), azimuth: this.pair ? 0.12 : 0.3, polar: 1.36 };
    }
  }

  fitScreen() {
    const narrow = this.stage.width < this.stage.height * 0.9;
    if (narrow === this.narrow) return false;
    this.narrow = narrow;
    if (CLUSTER_WHERE_SMALL_OR_STILL && narrow && !this.chosenShape) this.setShape("cluster", { chosen: false });
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

  /**
   * Show the two forms of the law side by side, under one clock, each lineage named by its run and
   * its form (the user's answer 9; "we'll wait for the real runs", 16 November 2026), or one.
   */
  setPair(on) {
    const next = Boolean(on) && Boolean(this.pairRuns);
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
      // A fission chosen (by a press, a key or the address) holds the clock there: the page does not then start it by itself.
      this.autoplayed = true;
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
    this.autoplayed = true;
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
        assembly: ASSEMBLY.clone().add(new THREE.Vector3(0, this.narrow ? 1.75 : this.pair ? 2.3 : 1.08, 0)),
        lineage: new THREE.Vector3(0, places.lineage.tapeY + 2.2, z - 2.6),
        molecules: new THREE.Vector3(places.table[0], 3.2, places.table[2]),
        population: new THREE.Vector3(places.population[0], 2.2, places.population[2]),
      }[level];
      // On a phone it wraps to two short lines, so that it finds room beside the page's card.
      this.tags.example = labels.add({ text: example, anchor, priority: 980, kind: `note label-region label-example${this.narrow ? " label-wrap" : ""}`, lift: 10 });
      this.tags.example.boost = 1000;
      this.tags.example.home = anchor.clone();
      this.exampleSpot = null;
    }
    if (level === "assembly" || (level === "lineage" && !this.narrow)) {
      const under = level === "assembly" ? (this.pair ? -2.05 : this.narrow ? -1.15 : -1.3) : this.pair || this.narrow ? -2.9 : -2.35;
      this.tags.shape = add({ id: `${PREFIX}assembly`, text: level === "lineage" ? "The assembly now: the shape is the picture's choice" : this.shapeWords(), anchor: ASSEMBLY.clone().add(new THREE.Vector3(0, under, 0)), priority: 520 });
      if (level === "assembly") {
        // The line on the picture that says what is the picture's own; while the founder gathers, the words for that in the shape's place.
        this.tags.own = labels.add({ text: OWN_WORDS, anchor: ASSEMBLY.clone().add(new THREE.Vector3(0, under - (this.narrow ? 0.45 : 0.42), 0)), priority: 960, kind: "note label-region label-own", lift: 0 });
        this.tags.own.boost = 900;
        this.tags.gather = labels.add({ text: GATHER_WORDS, anchor: ASSEMBLY.clone().add(new THREE.Vector3(0, under, 0)), priority: 940, kind: "part label-own", lift: 0 });
        this.tags.gather.hidden = true;
        this.tags.free = add({ text: "free molecules: the run's supply, held fixed", anchor: ASSEMBLY.clone().add(this.narrow ? new THREE.Vector3(1.6, 3.4, -2.5) : new THREE.Vector3(4.6, 1.3, -2.4)), priority: 330, lift: 0 });
      }
      // Each run of a pair is labelled with its own law, beneath its assembly.
      if (this.pair) for (const side of this.sides) add({ text: `${side.run.label}: ${formWords(side.run)}`, anchor: ASSEMBLY.clone().add(new THREE.Vector3(side.offset, 1.5, 0)), priority: 760, kind: "part label-wrap" });
      // At the lineages, each lineage of the pair is named too, beside its own fence.
      if (this.pair && level === "lineage") this.sides.forEach((side, index) => add({ text: `${side.run.label}: ${formWords(side.run)}`, anchor: new THREE.Vector3(this.placeAt.lineage.x1 + 0.6, 0.6, this.placeAt.lineage.z + index * 1.6), priority: 750 }));
    }
    if (level === "assembly") {
      this.tags.carries = add({ text: "carries on", anchor: new THREE.Vector3(), priority: 900, lift: 6 });
      this.tags.other = add({ text: "not followed", anchor: new THREE.Vector3(), priority: 880, lift: 6 });
      this.tags.carries.hidden = this.tags.other.hidden = true;
    }
    if (level === "lineage") {
      // On a phone the same names, in fewer words, so that each fits beside the others.
      const short = this.narrow;
      add({ id: `${PREFIX}part:tape`, text: short ? "The tape: each fission's parent" : "The tape: each fission's parent, types down from t000", anchor: new THREE.Vector3(short ? 1.5 : places.lineage.x0 + 3.2, short ? places.lineage.tapeY - places.lineage.tapeHeight / 2 + 0.45 : places.lineage.tapeY + places.lineage.tapeHeight / 2 + 0.25, z - 2.6), priority: 420 });
      add({ id: `${PREFIX}part:fence`, text: short ? "Similarity at each fission (the run's H)" : "Similarity at each fission: the run's own H", anchor: new THREE.Vector3(short ? 0 : places.lineage.x0 + 3, 4.3, z - 0.45), priority: 430 });
      const threshold = this.mainRun.threshold;
      if (threshold) this.tags.sheet = add({ id: `${PREFIX}threshold`, text: short ? `${threshold.value}: the analysis's threshold of inheritance` : `${threshold.value}: the analysis's threshold of inheritance`, anchor: new THREE.Vector3(short ? places.lineage.x1 - 2.4 : places.lineage.x1 - 1.5, 0.95 + ((threshold.value - 0.6) / 0.4) * 3.2, z - 0.45), priority: 440 });
      add({ id: `${PREFIX}part:spine`, text: short ? "The daughters that carry on" : "The lineage: the daughters that carry on", anchor: new THREE.Vector3(short ? 0 : places.lineage.x0 + 2.5, 0.1, z + 0.9), priority: 360 });
      add({ id: `${PREFIX}part:carpet`, text: short ? "The carpet: H of every two" : "The carpet: H of every two grown assemblies, worked out by the view", anchor: new THREE.Vector3(places.carpet[0], 0.2, places.carpet[2] + (short ? 2.1 : 2.5)), priority: 410 });
      add({ id: `${PREFIX}part:map`, text: short ? "The map: the picture's choice" : "The map: axes worked out by the view, the picture's choice", anchor: new THREE.Vector3(places.map[0], places.map[1] + (short ? 1.4 : 2.1), places.map[2]), priority: 400 });
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
    return this.shape === "micelle" ? "Lipids in a micelle, heads to the water and tails in: the shape is the picture's choice" : "Lipids in a loose cluster: the shape is the picture's choice";
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
    const chosen = chosenType ? Number(chosenType[1]) : null;
    this.sides.forEach((side, index) => {
      const { run, layout } = side;
      const phase = run.phaseAt(time);
      layout.mode = mode;
      // Where the assembly is not shown (the molecules, the population) its lipids are left where they are: back in view, they follow the run again.
      if (side.group.visible) {
        const rebuilt = layout.follow(run, phase);
        // At a run's start the founder's molecules gather from the water (the picture's own; with less motion it stands gathered).
        if (rebuilt && !still && this.level === "assembly" && phase.phase === "grow" && phase.g === 0 && phase.e === 0) layout.gather();
        moving = layout.step(seconds, { still }) || moving;
        side.meshes.draw(this.lipidsOf(side, index, phase), { tailColour: this.colours.lipidTail, chosen: chosen === null ? null : (lipid) => lipid.type === chosen && !lipid.free });
      }
      // The composition round the assembly: two groups during a split.
      const groups = phase.phase === "split"
        ? [{ x: run.carried(phase.k), centre: layout.centres[0], radius: layout.radius(layout.counts[0] || 40), fade: 0 }, { x: run.other(phase.k), centre: layout.centres[1], radius: layout.radius(layout.counts[1] || 40), fade: 0.75 * layout.fade }]
        : [{ x: run.compositionAt(time), centre: [0, 0, 0], radius: layout.radius(layout.counts[0] || 1), fade: 0 }];
      const key = `${phase.phase}:${phase.k}:${phase.e ?? ""}:${phase.phase === "split" ? phase.part.toFixed(3) : ""}:${this.shape}:${this.colours.version}`;
      // While the founder gathers its composition waits for it: the ring and the strip stand once it has gathered.
      side.ring.mesh.visible = this.composition === "wheel" && !layout.gathering;
      side.strip.mesh.visible = this.composition === "strip" && !layout.gathering;
      if (this.composition === "wheel") side.ring.draw(groups, style, key);
      else side.strip.draw(groups, style, key);
      const done = Math.min(run.fissionCount, Math.max(0, Math.floor(time + 1e-9)));
      side.fence.draw(done, this.compare, { chosen: chosenK ? Number(chosenK[1]) : null });
      side.spine.draw(done, phase.phase === "grow" ? phase.progress : 0, { chosen: chosenK ? Number(chosenK[1]) : null });
      side.done = done;
      side.phase = phase;
    });
    this.shade();
    const main = this.sides[0];
    this.tape.draw(main.done, this.colours.ramp);
    this.carpet.draw(main.done, this.colours.ramp);
    this.map.draw(main.done, this.mainRun.compositionAt(time), this.stage.camera);
    this.table.draw(this.colours.ramp, this.colours);
    if (this.tags?.gather) {
      this.tags.gather.hidden = !main.layout.gathering;
      if (this.tags.shape) this.tags.shape.hidden = main.layout.gathering;
      // On a phone there is room for one line under the assembly: while the founder gathers, that line says so (it says the picture's own too).
      if (this.tags.own) this.tags.own.hidden = this.narrow && main.layout.gathering;
    }
    this.placeSplitLabels(main);
    this.placeExample();
    this.stage.invalidate?.();
    return moving;
  }

  /**
   * The example's mark stands where the picture is free, whatever the level, the camera, the window
   * or the page's cards: the first place, from the top down, under the page's bar and clear of every
   * card that lies over the picture, as near the middle as it can. A point in the scene is found
   * there for it, at the depth of what the camera looks at. A page that names no cards (the page of its
   * own) has none in the way, and the mark still keeps under its bar's band.
   */
  placeExample() {
    const tag = this.tags?.example, stage = this.stage, labels = this.labels;
    if (!tag || !stage.camera || !stage.width || !stage.height || !tag.width || !labels?.keepClear) return;
    // The cards are measured again every half second, and at once when the window or the camera changed.
    const key = `${stage.width}x${stage.height}:${this.level}:${stage.camera.position.toArray().map((v) => v.toFixed(1)).join(",")}`;
    this.exampleFrames = (this.exampleFrames || 0) + 1;
    if (!this.exampleSpot || key !== this.exampleKey || this.exampleFrames > 30) {
      this.exampleFrames = 0;
      this.exampleKey = key;
      this.exampleSpot = this.freeSpot(tag.width, tag.height || 22, (typeof labels.blocked === "function" && labels.blocked()) || [], (labels.keepClear?.top ?? 56) + 8);
    }
    const spot = this.exampleSpot;
    if (!spot) { tag.anchor.copy(tag.home); return; }
    const centre = this.level === "assembly" ? ASSEMBLY : this.homeView().target;
    const depth = (this.scratch ??= new THREE.Vector3()).copy(centre).project(stage.camera).z;
    const y = spot.y + (tag.height || 22) + (tag.lift ?? 10);
    tag.anchor.set((spot.x / stage.width) * 2 - 1, 1 - (y / stage.height) * 2, Math.min(0.999, depth)).unproject(stage.camera);
  }

  /** The first free place, from the top down, for a box of this size: clear of the cards and inside the window. */
  freeSpot(width, height, cards, top) {
    const W = this.stage.width, H = this.stage.height, pad = 6;
    const meets = (box) => cards.some((card) => box.left < card.right && box.right > card.left && box.top < card.bottom && box.bottom > card.top);
    for (let y = top; y + height + pad < H; y += 10) {
      for (const share of [0.5, 0.42, 0.58, 0.34, 0.66, 0.26, 0.74, 0.86, 0.14]) {
        const x = Math.min(W - width / 2 - pad, Math.max(width / 2 + pad, W * share));
        if (!meets({ left: x - width / 2 - pad, top: y - pad, right: x + width / 2 + pad, bottom: y + height + pad })) return { x, y };
      }
    }
    return null;
  }

  /** The lipids one side draws now: its assembly's, the daughter it let go, and (on the main side, round one assembly) the free molecules. */
  lipidsOf(side, index, phase) {
    const { layout, group } = side;
    const pool = side.pool || (side.pool = []);
    const haze = this.colours.haze, tail = this.colours.lipidTail;
    let used = 0;
    const take = () => pool[used++] || (pool[used - 1] = { pos: [0, 0, 0], axis: [0, 1, 0], colour: new THREE.Color(), tint: new THREE.Color() });
    const headOf = (type) => {
      const slot = this.leading.indexOf(type);
      return slot >= 0 ? this.colours.lead[slot] : type % 2 ? this.colours.otherAlt : this.colours.other;
    };
    const put = (bead, fade, free = false) => {
      const lipid = take();
      const slot = this.leading.indexOf(bead.type);
      lipid.type = bead.type;
      lipid.free = free;
      lipid.slot = slot >= 0 ? slot : 3;
      for (let a = 0; a < 3; a++) { lipid.pos[a] = bead.pos[a]; lipid.axis[a] = (bead.axis || bead.dir)[a]; }
      lipid.spin = bead.spin || 0;
      lipid.phase = bead.phase || 0;
      lipid.scale = bead.scale ?? 1;
      lipid.tail = bead.tailLength ?? 0.6;
      lipid.flex = bead.flex ?? 1;
      // A molecule that has just come glows where it is; one seeping in or out has a faint halo while it moves.
      lipid.glow = bead.glow > 0 ? bead.glow / GLOW_S : bead.flight < 1 && !layout.gathering ? 0.25 + 0.5 * Math.sin(Math.PI * bead.flight) : 0;
      lipid.colour.copy(headOf(bead.type)).lerp(haze, fade);
      lipid.tint.copy(tail).lerp(haze, fade);
      return lipid;
    };
    const out = this.drawn?.[index] || [];
    out.length = 0;
    for (const bead of layout.beads) if (bead.pos) out.push(put(bead, bead.side === 1 ? 0.7 * layout.fade : 0));
    for (const bead of layout.adrift) out.push(put(bead, bead.fade ?? 0.8));
    if (index === 0 && this.level === "assembly" && !this.pair) {
      const eye = this.stage.camera ? [this.stage.camera.position.x, this.stage.camera.position.y, this.stage.camera.position.z] : null;
      const centre = [group.position.x, group.position.y, group.position.z];
      for (const free of this.crowd.at(this.waterTime, centre, eye)) {
        free.pos = [free.pos[0] - centre[0], free.pos[1] - centre[1], free.pos[2] - centre[2]];
        free.tailLength = 0.55;
        free.flex = 1.5;
        out.push(put(free, 0.18, true));
      }
    }
    (this.drawn ??= [])[index] = out;
    return out;
  }

  /** The shade deep inside each assembly shown (the water's own stand-in for contact shade). */
  shade() {
    const cores = this.lipid.heads.userData.wetUniforms.uCores.value;
    const tails = this.lipid.tails.userData.wetUniforms.uCores.value;
    let at = 0;
    for (const side of this.sides) {
      if (!side.group.visible) continue;
      for (let s = 0; s < 2 && at < cores.length; s++) {
        const count = side.layout.counts[s];
        if (!count) continue;
        const c = side.layout.centres[s], r = side.layout.radius(count) * 1.05;
        cores[at].set(side.group.position.x + c[0], side.group.position.y + c[1], side.group.position.z + c[2], this.shape === "micelle" ? r : 0);
        tails[at].copy(cores[at]);
        at++;
      }
    }
    for (; at < cores.length; at++) { cores[at].w = 0; tails[at].w = 0; }
  }

  placeSplitLabels(side) {
    if (!this.tags?.carries) return;
    const splitting = side.phase?.phase === "split" && side.phase.part > 0.2;
    this.tags.carries.hidden = this.tags.other.hidden = !splitting;
    // While the daughters part, their words stand where the shape's do.
    if (this.tags.shape && splitting) this.tags.shape.hidden = true;
    else if (this.tags.shape && !side.layout.gathering) this.tags.shape.hidden = false;
    if (!splitting) return;
    const { layout, group } = side;
    // Beneath each daughter, or beside it where the daughters part up and down.
    const below = (centre, count) => (layout.axis === 1
      ? new THREE.Vector3(centre[0] + layout.radius(count || 40) * 1.7 + 0.3, centre[1], centre[2])
      : new THREE.Vector3(centre[0], centre[1] - layout.radius(count || 40) - 0.42, centre[2])).add(group.position);
    this.tags.carries.anchor.copy(below(layout.centres[0], layout.counts[0]));
    this.tags.other.anchor.copy(below(layout.centres[1], layout.counts[1]));
  }

  /**
   * Hold the picture where it is (for pictures and checks): the clock is not ticked and nothing
   * eases on by itself; `advance(seconds)` then moves what moves by a fixed step.
   */
  hold(on = true) {
    this.held = Boolean(on);
    this.stage.invalidate?.();
  }

  advance(seconds, steps = 8) {
    for (let i = 0; i < steps; i++) this.sync(seconds / steps);
    this.stage.invalidate?.();
  }

  update(dt = 16, time, real = dt) {
    if (this.stage.width && this.stage.height && this.fitScreen()) return true;
    if (this.held) {
      this.sync(0);
      return false;
    }
    // The water moves by the stage's clock of decoration, which stands for less motion and while the page holds it.
    const decoration = this.stage.decoration;
    const flowing = Boolean(this.active && decoration?.moving);
    if (decoration) this.waterTime = decoration.time;
    this.water.setTime(this.waterTime);
    if (this.stage.camera) {
      this.water.face(this.stage.camera);
      // Nothing nearer than what the camera looks at is hazed.
      const subject = this.level === "assembly" ? ASSEMBLY : this.homeView().target;
      this.water.setHazeNear(this.stage.camera.position.distanceTo(subject) + (this.level === "assembly" ? 1.4 : 4));
    }
    if (this.stage.height) this.water.setViewport(this.stage.height, this.stage.renderer?.getPixelRatio?.() || 1);
    // While the founder gathers the clock stands at the run's start; then, where the page asks, it plays.
    const gathering = this.sides.some((side) => side.layout.gathering);
    const playing = this.active && !gathering ? this.player.tick(real) : false;
    if (this.active && this.autoplay && !gathering && !this.autoplayed && !this.stage.reducedMotion) {
      this.autoplayed = true;
      this.player.play();
    }
    const moving = this.sync(dt / 1000);
    return playing || moving || flowing || gathering;
  }

  // ------------------------------------------------------------ theme and cost

  applyPalette(palette) {
    this.palette = palette;
    const tokens = readTokens(this.stage.host, palette);
    this.tokens = tokens;
    const tone = (value) => new THREE.Color(value || "#888888");
    const ramp = tokens.ramp.map(tone);
    const water = WATER_THEMES[palette.dark ? "dark" : "light"];
    this.water.setTheme(Boolean(palette.dark));
    this.colours = {
      lead: tokens.lead.map(tone), other: tone(tokens.other), otherAlt: tone(tokens.otherAlt), tail: tone(tokens.tail),
      lipidTail: tone(tokens.lipidTail), haze: tone(water.mid),
      stage: tone(water.mid), chosen: tone(palette.accent), ramp, version: (this.colours?.version || 0) + 1,
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
    // The halo of a molecule that comes or goes: light added in dark water, a soft tint laid over in pale water.
    this.lipid.glow.uniforms.color.value.set(tokens.glow);
    this.lipid.glow.blending = palette.dark ? THREE.AdditiveBlending : THREE.NormalBlending;
    this.lipid.glow.uniforms.opacity.value = palette.dark ? 0.42 : 0.3;
    this.lipid.glow.needsUpdate = true;
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

  /** What one frame costs to draw, counted from the scene: draws and triangles of every visible thing, the water's too. */
  cost() {
    let draws = 0, triangles = 0;
    const count = (object) => {
      if (!(object.isMesh || object.isLine || object.isPoints)) return;
      const geometry = object.geometry;
      const instances = object.isInstancedMesh ? object.count : 1;
      if (instances === 0) return;
      const range = geometry.drawRange.count === Infinity ? (geometry.index ? geometry.index.count : geometry.attributes.position.count) : geometry.drawRange.count;
      if (range === 0) return;
      draws += 1;
      if (object.isMesh) triangles += (range / 3) * instances;
    };
    this.root.traverseVisible(count);
    if (this.water.attached) this.water.group.traverseVisible(count);
    return { draws, triangles: Math.round(triangles) };
  }

  dispose() {
    this.stopLook?.();
    if (this.listening) for (const name of ["time", "state"]) this.player.removeEventListener(name, this.listening);
    this.water.detach();
    this.water.dispose();
    for (const material of Object.values(this.lipid)) material.dispose();
    disposeTree(this.root);
    this.environment?.dispose?.();
    this.studio?.dispose?.();
  }
}
