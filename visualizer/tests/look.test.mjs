// The resting look of the Cell view (src/core/look.js, passes.js, materials.js): which
// effects are drawn, what a device that cannot keep up gives up and in what order, the
// clock of decoration, what takes part in contact shade, and what the shader hooks add.
// The drawing itself is checked with real input by tools/check_look.mjs.

import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";
import * as THREE from "three";
import { Look, Decoration, EFFECTS, STEPS, SLOW_MS, WINDOW, SETTLE } from "../src/core/look.js";
import { soften, enrich, jostle, lookNumbers, TEXTURES } from "../src/core/materials.js";
import { solid, Finish } from "../src/core/passes.js";
import { Stage } from "../src/core/stage.js";
import { CellLens, LOOK } from "../src/lenses/cell.js";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const read = (file) => readFileSync(path.join(ROOT, file), "utf8");
const SEVEN = ["reflections", "filmic", "translucency", "contact", "texture", "drift", "shimmer"];

/** Feed a look frames of one length: the frames it lets pass first, then full windows. */
function frames(look, milliseconds, windows = 1) {
  let stepped = 0;
  for (let index = 0; index < SETTLE + WINDOW * windows; index++) if (look.frame(milliseconds)) stepped += 1;
  return stepped;
}

test("the seven effects the user chose, and no bloom among them", () => {
  assert.deepEqual(EFFECTS.map((effect) => effect.id), SEVEN);
  for (const effect of EFFECTS) assert.ok(effect.label && effect.cost, `${effect.id} says what it is and what a frame pays for it`);
  assert.ok(!EFFECTS.some((effect) => /bloom/i.test(effect.id + effect.label)), "bloom is kept for flux");
});

test("a view that does not ask keeps the look it had; one that asks gets all seven", () => {
  const look = new Look();
  assert.equal(look.choice, "rich", "rich is the default choice");
  assert.deepEqual(look.drawn(), [], "but nothing is drawn for a view that has not asked");
  assert.equal(look.contact, 0);
  look.want(true);
  assert.deepEqual(look.drawn(), SEVEN);
  assert.equal(look.contact, 1);
  assert.equal(look.says(), null, "all that was chosen is drawn: nothing to say");
  look.want(false);
  assert.deepEqual(look.drawn(), []);
});

test("plain is the look as it was; choosing is told to whoever listens", () => {
  const look = new Look();
  let told = 0;
  look.onChange(() => (told += 1));
  look.want(true);
  assert.equal(look.choose("plain"), true);
  assert.deepEqual(look.drawn(), []);
  assert.equal(look.says(), null);
  assert.equal(look.choose("rich"), true);
  assert.deepEqual(look.drawn(), SEVEN);
  assert.equal(look.choose("gaudy"), false, "an unknown word changes nothing");
  assert.deepEqual(look.drawn(), SEVEN);
  assert.equal(told, 3);
});

test("a device that cannot keep up gives up contact shade at half size, then all of it, then the rest; never the other way", () => {
  const look = new Look();
  look.want(true);
  assert.equal(frames(look, 12, 4), 0, "fast frames: nothing is given up");
  assert.equal(look.step, 0);
  // Slow frames, a window at a time.
  assert.equal(frames(look, 60), 1);
  assert.equal(look.contact, 0.5, "first, contact shade at half size");
  assert.deepEqual(look.drawn(), SEVEN, "every effect is still drawn");
  assert.match(look.says(), /half size/);
  assert.equal(frames(look, 60), 1);
  assert.equal(look.contact, 0, "then contact shade off");
  assert.deepEqual(look.drawn(), SEVEN.filter((id) => id !== "contact"));
  assert.match(look.says(), /Contact shade is off/);
  assert.equal(frames(look, 60), 1);
  assert.deepEqual(look.drawn(), ["reflections", "filmic"], "then the rest of what costs something in each frame");
  assert.match(look.says(), /Only studio reflections and filmic light/);
  assert.equal(frames(look, 60, 3), 0, "there is no further step");
  assert.equal(look.step, STEPS.length - 1);
  assert.equal(frames(look, 5, 6), 0, "and fast frames never bring anything back by themselves");
  assert.deepEqual(look.drawn(), ["reflections", "filmic"]);
  // The visitor choosing the look again starts afresh.
  look.choose("rich");
  assert.deepEqual(look.drawn(), SEVEN);
  assert.equal(look.contact, 1);
});

test("the judgement is the middle frame of a window, after the frames that are let pass", () => {
  const look = new Look();
  look.want(true);
  for (let index = 0; index < SETTLE; index++) assert.equal(look.frame(400), false, "the first frames after a change are let pass: shaders compile");
  for (let index = 0; index < WINDOW - 1; index++) assert.equal(look.frame(SLOW_MS * 1.5), false);
  assert.equal(look.frame(SLOW_MS * 1.5), true, "a full window of slow frames steps down");
  // A single slow frame among fast ones does not.
  const steady = new Look();
  steady.want(true);
  for (let index = 0; index < SETTLE + WINDOW * 3; index++) steady.frame(index % WINDOW === 3 ? 100 : 14);
  assert.equal(steady.step, 0);
  // Nor a burst of long frames while a part is built or its shaders compile: fewer than half the window.
  const hitched = new Look();
  hitched.want(true);
  for (let index = 0; index < SETTLE + WINDOW * 3; index++) hitched.frame(index % WINDOW < 20 ? 100 : 14);
  assert.equal(hitched.step, 0, "twenty long frames in forty-five say nothing of the device");
  // A browser that holds the page to thirty frames a second is not a device that cannot keep up.
  const capped = new Look();
  capped.want(true);
  for (let index = 0; index < SETTLE + WINDOW * 4; index++) capped.frame(1000 / 30 + (index % 2 ? 0.4 : -0.4));
  assert.equal(capped.step, 0);
  // One that manages twenty does step down.
  const slow = new Look();
  slow.want(true);
  for (let index = 0; index < SETTLE + WINDOW; index++) slow.frame(50);
  assert.equal(slow.step, 1);
  assert.equal(SLOW_MS, 40, "not smooth means under twenty-five frames a second");
});

test("held: every effect stays on whatever the frame rate (the word 'full', and a switch set by hand)", () => {
  const full = new Look();
  full.want(true);
  full.choose("full");
  assert.equal(frames(full, 200, 5), 0);
  assert.deepEqual(full.drawn(), SEVEN);
  assert.equal(full.says(), null);
  const tried = new Look();
  tried.want(true);
  tried.set("contact", false);
  assert.deepEqual(tried.drawn(), SEVEN.filter((id) => id !== "contact"));
  assert.equal(tried.contact, 0);
  assert.equal(frames(tried, 200, 5), 0, "the visitor is judging: the fallback rests");
  tried.set("contact", true);
  assert.equal(tried.contact, 1);
  tried.set("sparkle", true);
  assert.deepEqual(tried.drawn(), SEVEN, "an unknown effect is not one");
  tried.choose("rich");
  assert.equal(tried.held, false, "choosing the look again hands the judging back");
});

test("decoration stands still for reduced motion and while anything holds it", () => {
  const clock = new Decoration();
  assert.equal(clock.tick(500), true);
  assert.equal(clock.time, 0.5);
  clock.pause("flux");
  clock.pause("flux");
  assert.equal(clock.moving, false);
  assert.equal(clock.tick(500), false);
  assert.equal(clock.time, 0.5, "held: the clock does not run");
  clock.pause("another");
  clock.resume("flux");
  assert.equal(clock.moving, false, "still held by the other");
  clock.resume("another");
  assert.equal(clock.tick(250), true);
  assert.equal(clock.time, 0.75);
  const still = new Decoration({ still: true });
  assert.equal(still.tick(1000), false);
  assert.equal(still.time, 0);
});

test("what takes part in contact shade: solid parts only", () => {
  const part = (options, data = {}) => Object.assign(new THREE.MeshStandardMaterial(options), { userData: data });
  assert.equal(solid(part({}, { solidDepth: true })), true, "a solid part");
  assert.equal(solid(part({ transparent: true, opacity: 0.78 }, { solidDepth: true })), true, "the nucleus: a little clear, made to hide what lies behind it");
  assert.equal(solid(part({ transparent: true, opacity: 0.44, depthWrite: false }, { solidDepth: false })), false, "glass takes no part");
  assert.equal(solid(part({ transparent: true, opacity: 0.14 }, { solidDepth: true })), false, "nor a part dimmed while another is in focus");
  assert.equal(solid(part({}, { solidDepth: true, sketch: true })), false, "nor a sketch");
  assert.equal(solid(part({}, { solidDepth: true, noContact: true })), false, "nor what drifts");
  assert.equal(solid(new THREE.MeshBasicMaterial({ colorWrite: false })), false, "nor a body that is only there to be clicked");
  assert.equal(solid(new THREE.MeshBasicMaterial({ wireframe: true })), false);
  assert.equal(solid(part({ depthWrite: true, transparent: true, opacity: 0.8 })), true, "scenery made solid counts by what it was made to be");
  assert.equal(solid(null), false);
  assert.equal(solid([part({})]), false);
});

test("the finishing passes cost nothing until asked for, and bloom shines only from what was marked", () => {
  const finish = new Finish({});
  assert.equal(finish.active, false);
  finish.setContact(0.5, { reach: 2 });
  assert.equal(finish.active, true);
  assert.equal(finish.contact.reach, 2);
  finish.setContact(0);
  assert.equal(finish.active, false);
  finish.setBloom(0.6, { radius: 0.4 });
  assert.equal(finish.active, true);
  assert.equal(finish.bloom.radius, 0.4);
  const bead = new THREE.Group(), child = new THREE.Mesh(), other = new THREE.Mesh();
  bead.add(child);
  finish.glow(bead);
  assert.equal(finish.shines(child), true, "what a marked thing holds shines with it");
  assert.equal(finish.shines(other), false);
  finish.glow(bead, false);
  assert.equal(finish.shines(child), false);
  finish.setBloom(0);
  assert.equal(finish.active, false);
});

/** Run a material's hook on a stand-in for a shader, as the renderer would. */
function compiled(material) {
  const shader = {
    uniforms: {},
    vertexShader: "#include <common>\nvoid main() {\n#include <begin_vertex>\n#include <project_vertex>\n}",
    fragmentShader: "#include <common>\nvoid main() {\n#include <color_fragment>\n#include <normal_fragment_begin>\n#include <normal_fragment_maps>\n#include <opaque_fragment>\n}",
  };
  material.onBeforeCompile(shader, null);
  return shader;
}

test("the soft rim is as it was: the other views' materials compile to the same shader", () => {
  const material = soften(new THREE.MeshStandardMaterial(), { rim: 0.3, alphaRim: 0.2 });
  const shader = compiled(material);
  assert.equal(material.customProgramCacheKey(), "cells-soft-rim");
  assert.deepEqual(Object.keys(shader.uniforms), ["uRimColor", "uRimStrength", "uRimPower", "uAlphaRim"]);
  assert.ok(!/uLook|vLookPos/.test(shader.vertexShader + shader.fragmentShader), "nothing of the look is in it");
  assert.equal(shader.vertexShader, "#include <common>\nvoid main() {\n#include <begin_vertex>\n#include <project_vertex>\n}", "its vertex shader is untouched");
});

test("an enriched material: light through thin parts, a texture, a shimmer, each switched by a shared number", () => {
  const numbers = lookNumbers();
  assert.deepEqual(Object.keys(numbers), ["time", "translucency", "texture", "shimmer", "drift"]);
  for (const value of Object.values(numbers)) assert.equal(value.value, 0, "all off until a view asks");
  const nucleus = enrich(new THREE.MeshStandardMaterial(), numbers, { rim: 0.55, thin: 0.9, texture: "pores", unit: 2 });
  const shader = compiled(nucleus);
  assert.equal(shader.uniforms.uLookTranslucency, numbers.translucency, "the switch is the stage's own number, not a copy");
  assert.equal(shader.uniforms.uLookTexture, numbers.texture);
  assert.equal(shader.uniforms.uLookShimmer, numbers.shimmer);
  assert.equal(shader.uniforms.uLookTime, numbers.time);
  assert.equal(shader.uniforms.uLookThin.value, 0.9);
  assert.equal(shader.uniforms.uLookUnit.value, 2);
  assert.equal(shader.uniforms.uRimStrength.value, 0.55, "the soft rim is kept");
  assert.equal(nucleus.userData.rim.uRimColor, shader.uniforms.uRimColor, "the lens still finds the rim's colour");
  assert.match(shader.fragmentShader, /#define LOOK_TEXTURE 3\n#define LOOK_THIN\n/);
  assert.ok(!shader.fragmentShader.includes("#define LOOK_SHIMMER"));
  assert.match(shader.vertexShader, /vLookPos = position;/);
  // With every shared number at 0, nothing of the look changes the picture: each term is behind its switch.
  assert.match(shader.fragmentShader, /if \(uLookTexture > 0\.0\)/);
  assert.match(shader.fragmentShader, /if \(lookOn > 0\.0\)/);
  assert.match(shader.fragmentShader, /if \(uLookTranslucency > 0\.0\)/);
  // The pieces stand where the renderer's own pieces were, each of which is kept.
  for (const piece of ["#include <common>", "#include <color_fragment>", "#include <normal_fragment_maps>", "#include <opaque_fragment>"]) assert.ok(shader.fragmentShader.includes(piece), piece);
  assert.ok(shader.fragmentShader.indexOf("lookThrough") < shader.fragmentShader.indexOf("#include <opaque_fragment>"), "light is added before the colour is written out");

  const membrane = enrich(new THREE.MeshStandardMaterial(), numbers, { shimmer: true });
  assert.match(compiled(membrane).fragmentShader, /#define LOOK_TEXTURE 0\n#define LOOK_SHIMMER\n/);
  const keys = new Set([nucleus, membrane, enrich(new THREE.MeshStandardMaterial(), numbers, { thin: 0.5 }), enrich(new THREE.MeshStandardMaterial(), numbers, { texture: "folds", thin: 0.7 })].map((material) => material.customProgramCacheKey()));
  assert.equal(keys.size, 4, "materials that differ in what they ask for do not share a shader");
  assert.equal(enrich(new THREE.MeshStandardMaterial(), numbers, { texture: "grain", thin: 0.8 }).customProgramCacheKey(), enrich(new THREE.MeshStandardMaterial(), numbers, { texture: "grain", thin: 0.2 }).customProgramCacheKey(), "and those that ask for the same do");
  assert.deepEqual(TEXTURES, ["grain", "folds", "pores"]);
  assert.equal(enrich(new THREE.MeshStandardMaterial(), numbers, { texture: "marble" }).userData.look.texture, null, "an unknown texture is none");
});

test("the membrane's shimmer flickers in place: its pace depends on the place, never the place on the time", () => {
  const source = read("src/core/materials.js");
  const beat = /#define LOOK_BEAT\(o\) (.*)/.exec(source)[1];
  assert.match(beat, /sin\(t \* \(.*lookHash\(i \+ o.*\)\) \+ .*lookHash\(i \+ o\)\)/, "each lattice point: a sine of the time, at its own pace and phase");
  assert.ok(!/p\s*[+-]\s*t|t\s*\*\s*p|p\.[xyz]\s*[+-]\s*uLookTime/.test(source), "no term moves the pattern across the sheet as a wave would");
});

test("crowd drift: bounded, with no net direction, and out of contact shade", () => {
  const numbers = lookNumbers();
  const points = jostle(new THREE.PointsMaterial(), numbers, { reach: 0.1 });
  const shader = compiled(points);
  assert.equal(shader.uniforms.uLookDrift, numbers.drift);
  assert.equal(shader.uniforms.uLookTime, numbers.time);
  assert.equal(shader.uniforms.uLookReach.value, 0.1);
  assert.match(shader.vertexShader, /if \(uLookDrift > 0\.0\) transformed \+= uLookDrift \* uLookReach \* lookJostle\(lookSeed, uLookTime\);/);
  assert.equal(points.userData.noContact, true);
  // The jostle is sines of the time alone: each has mean nothing, so the crowd goes nowhere.
  const jostled = /vec3 lookJostle\(vec3 seed, float t\) \{\s*return (.*);/.exec(read("src/core/materials.js"))[1];
  const terms = jostled.match(/sin\([^)]*\)/g);
  assert.equal(terms.length, 6);
  for (const term of terms) assert.match(term, /^sin\(t \* [0-9.]+ \+ seed\.[xyz] \* [0-9.]+\)$/, `${term}: a sine of the time, set off by the place`);
  assert.ok(!/[^a-z]t\s*\*\s*[0-9.]+\s*[;,)]/.test(jostled.replace(/sin\([^)]*\)/g, "S")), "no term grows with the time");
  // In numbers: over a long while, the mean displacement of a point is next to nothing beside its reach.
  const rates = terms.map((term) => Number(/t \* ([0-9.]+)/.exec(term)[1]));
  let sum = 0, peak = 0;
  for (let step = 0; step < 200000; step++) {
    const t = step * 0.01, x = Math.sin(t * rates[0] + 1.3) + Math.sin(t * rates[1] + 0.4);
    sum += x;
    peak = Math.max(peak, Math.abs(x));
  }
  assert.ok(Math.abs(sum / 200000) < 0.01 && peak <= 2, `a point's mean is ${sum / 200000} and it never leaves its reach (${peak})`);

  // A material that already has a soft rim keeps it: the drift runs after it.
  const numbersTwo = lookNumbers();
  const speck = jostle(soften(new THREE.MeshStandardMaterial(), { rim: 0.3 }), numbersTwo, { reach: 0.13 });
  const both = compiled(speck);
  assert.ok(both.uniforms.uRimColor && both.uniforms.uLookDrift, "both hooks ran");
  assert.equal(speck.customProgramCacheKey(), "cells-soft-rim|cells-jostle");
  assert.match(both.vertexShader, /instanceMatrix\[3\]\.xyz/, "a copy of an instanced shape is set off by where the copy stands");
});

test("the cell's parts ask for the look where the user chose it, and for nothing where no data would excuse it", () => {
  const parts = ["src/lenses/cell_parts.js", ...readdirSync(path.join(ROOT, "src", "lenses", "parts")).filter((name) => name.endsWith(".js")).sort().map((name) => `src/lenses/parts/${name}`)].map(read).join("\n"), structures = read("src/lenses/cell_structures.js"); // the builder and its part modules
  const asks = (pattern) => assert.match(parts, pattern);
  asks(/membrane\.material\(\{ hue: "bioMembrane", opacity: style\.shellOpacity,[^}]*shimmer: true \}\)/); // the membrane shimmers
  assert.match(structures, /envelope\.material\(\{ hue: "bioNucleus", opacity: 0\.74,[^}]*texture: "pores" \}\)/); // pores on the nucleus
  assert.match(structures, /er\.material\(\{ hue: "bioEr",[^}]*texture: "grain" \}\)/); // grain on the ER's sheets
  assert.equal((parts.match(/texture: "folds"/g) || []).length, 1, "folds on a mitochondrion left whole");
  // One cut open shows its shelves themselves; its shell stays out of contact shade, so the rim keeps its light.
  asks(/const outer = mitochondria\.material\(\{ hue: "bioMito", clip: true, side: THREE\.DoubleSide,[^}]*contact: false \}\)/);
  assert.match(read("src/lenses/cell.js"), /if \(!contact\) material\.userData\.noContact = true;/);
  asks(/chemistry\.material\(\{ hue: "bioCyto", shade: -0\.3, drift: [0-9.]+ \}\)/); // the cytosol's crowd drifts
  asks(/chemistry\.points\(\{ hue: "bioCyto",[^}]*drift: [0-9.]+ \}\)/);
  // A planned part is drawn whole where colour shows the kind of part, with the look, and is a sketch where colour
  // shows status (the user, 16 November 2026): each of its materials has a twin, a wire mesh, that colour() swaps in.
  const lens = read("src/lenses/cell.js");
  assert.match(lens, /get sketching\(\) \{\s*return this\.status === "planned" && this\.lens\.colourBy === "status";/);
  assert.match(lens, /if \(!sketch && this\.status === "planned"\) \{\s*\/\/[^\n]*\n\s*const twin = new THREE\.MeshBasicMaterial\(\{ wireframe: true,/);
  assert.match(lens, /this\.group\.userData\.seeThrough = sketching;/, "picked through only while it is a sketch");
  assert.match(structures, /golgi\.material\(\{ hue: "bioGolgi",[^}]*texture: "grain" \}\)/, "the Golgi, planned, takes the look like any part");
  // A sketch asked for in so many words, and a data mark, get none of it.
  for (const source of [parts, structures]) {
    for (const [use] of source.matchAll(/\.material\(\{[^}]*\b(?:line|wire): true[^}]*\}\)/g)) assert.ok(!/thin|texture|shimmer|drift/.test(use), `${use}: a sketch stays a sketch`);
  }
  // What drifts is the crowd, never what enters or leaves the cell.
  for (const flowing of ["water.material", "secretion.material", "outside.material", "medium.material", "fuel.points", "fuel.material"]) {
    for (const use of parts.match(new RegExp(`${flowing.replace(".", "\\.")}\\([^)]*\\)`, "g")) || []) assert.ok(!/drift/.test(use), `${use}: not part of the drifting crowd`);
  }
});

test("only the Cell view asks for the look; the page says what is scenery and what is given up", () => {
  const asking = ["proteins.js", "shelves_view.js", "stack.js", "replay.js"].filter((name) => /\.dress\(|enrich\(|jostle\(|makeStudio\(/.test(read(path.join("src", "lenses", name))));
  assert.deepEqual(asking, [], "the other views keep the look they had");
  const lens = read("src/lenses/cell.js");
  assert.match(lens, /this\.stage\.dress\(\{ rich: false \}\)/, "and the Cell view hands the stage back as it found it");
  assert.match(lens, /filmic: this\.colourBy === "biology"/, "filmic light is for natural colours: status colours stay as the legend shows them");
  assert.match(lens, /material\.toneMapped = !data\.sketch && !\(data\.emissive > 0\);/, "a sketch's grey says planned: it stays out too, and so does what gives off its own light");
  const viewer = read("src/ui/viewer.js");
  // The switch stands by the scale bar, where it takes no room from the labels' column; the card and the legend are as they were.
  assert.match(viewer, /h\("div", \{ class: "look-switch card" \}, this\.segmented\("Look", \[\["rich", "Rich"\], \["plain", "Plain"\]\]/);
  assert.match(viewer, /this\.scaleBar = h\("div", \{ class: "scalebar", hidden: true \}, this\.lookBox, this\.scaleLine, this\.scaleText\);/);
  assert.equal((viewer.match(/this\.segmented\("Look"/g) || []).length, 1, "one switch, and not a row of the view's card");
  assert.match(viewer, /note = \{ swatch: "illustration", text \};/, "the legend's note is as it was");
  assert.match(viewer, /query\.get\("look"\)/);
  assert.match(viewer, /query\.get\("fps"\)/);
  const styles = read("src/ui/styles.js");
  assert.match(styles, /\.look-switch \{[^}]*pointer-events: auto;/, "the scale bar lets the pointer through to the picture; the switch takes it");
  assert.ok(!/\.look-(box|note) \{[^}]*pointer-events/.test(styles), "and the words beside it do not: a drag may start on them");
  for (const step of STEPS.slice(1)) assert.match(step.says, /this device could not keep the picture moving smoothly/, "each step says why, in plain words");
});

test("what the page says beside the switch: scenery in the legend's own word, what was given up, and motion held still", () => {
  const look = new Look(), decoration = new Decoration();
  const notes = () => CellLens.prototype.lookChrome.call({ stage: { look, decoration } });
  assert.deepEqual(notes(), { active: "rich", notes: [] }, "a view that has not asked says nothing");
  look.want(true);
  assert.deepEqual(notes().notes, ["Surface texture, the crowd's slow jostling and the membrane's shimmer are scenery."]);
  decoration.still = true;
  assert.deepEqual(notes().notes, ["Surface texture is scenery.", "The crowd and the membrane are held still: this device asks for less motion."], "what does not move is not called motion");
  decoration.still = false;
  look.set("texture", false);
  assert.deepEqual(notes().notes, ["The crowd's slow jostling and the membrane's shimmer are scenery."]);
  look.set("drift", false);
  assert.deepEqual(notes().notes, ["The membrane's shimmer is scenery."]);
  look.choose("rich");
  frames(look, 60);
  assert.equal(notes().notes.length, 2);
  assert.match(notes().notes[1], /^Contact shade is drawn at half size: this device could not keep/);
  frames(look, 60);
  frames(look, 60);
  assert.deepEqual(notes().notes.map((text) => text.slice(0, 44)), ["Only studio reflections and filmic light are"], "a texture that is no longer drawn is no longer named");
  look.choose("plain");
  assert.deepEqual(notes(), { active: "plain", notes: [] });
  for (const lens of ["cell.js"]) assert.ok(!/So are the texture/.test(read(path.join("src", "lenses", lens))));
});

test("contact shade reaches a little way only, and never shades from far behind: the pass follows the scene's scale", () => {
  const finish = new Finish({});
  const scene = new THREE.Scene(), camera = new THREE.PerspectiveCamera(34, 4 / 3, 0.1, 5000);
  finish.setSize(800, 600);
  finish.setContact(1, { reach: 0.3, strength: 0.5 });
  const pass = finish.contactPass(scene, camera);
  assert.equal(pass.output, pass.constructor.OUTPUT.Off, "the pass lays nothing over anything itself");
  assert.deepEqual([finish.contact.picture.width, finish.contact.picture.height], [800, 600], "its pictures are the page's size");
  assert.ok(finish.contact.picture.depthTexture, "with the solid parts' depth beside their facing");
  const numbers = pass.gtaoMaterial.uniforms;
  assert.equal(numbers.radius.value, 0.3, "it reaches as far as the view says");
  assert.equal(numbers.thickness.value, 0.3, "and a thing farther behind than that is another part in front, not a part touching");
  assert.equal(numbers.scale.value, 1, "the shade is as worked out, not deepened");
  assert.equal(pass.pdMaterial.uniforms.depthPhi.value, 0.6, "the smoothing stays on one surface at the scene's own scale");
  // A small cell: every length follows.
  finish.setContact(0.5, { reach: 0.011 });
  finish.contactPass(scene, camera);
  assert.deepEqual([finish.contact.picture.width, finish.contact.picture.height], [400, 300], "at half size its pictures are half the page's each way");
  assert.equal(numbers.radius.value, 0.011);
  assert.equal(numbers.thickness.value, 0.011);
  assert.ok(Math.abs(pass.pdMaterial.uniforms.depthPhi.value - 0.022) < 1e-12);
  assert.equal(finish.contact.strength, 0.5, "what was not said again stays");
  // The view's own numbers: gentle, and bounded on the screen.
  assert.ok(LOOK.reach > 0.2 && LOOK.reach < 0.9 && LOOK.shade > 0.3 && LOOK.shade < 0.8, "under a micrometre, and well under full strength");
  const lens = { u: 1, sizeMode: "schematic", stage: { rig: { distance: 52 } } };
  assert.equal(CellLens.prototype.reachNow.call(lens), LOOK.reach, "at the cell's own distance: the reach in micrometres");
  lens.sizeMode = "real";
  assert.equal(CellLens.prototype.reachNow.call(lens), LOOK.reachToScale, "to scale, where parts are smaller and closer, a shorter reach");
  assert.ok(LOOK.reachToScale < LOOK.reach / 2);
  lens.sizeMode = "schematic";
  lens.stage.rig.distance = 4;
  assert.equal(CellLens.prototype.reachNow.call(lens), LOOK.reachOnScreen * 4, "close up: a share of the distance, so that it never grows on the screen");
  lens.u = 0.02;
  lens.stage.rig.distance = 1.04;
  assert.equal(CellLens.prototype.reachNow.call(lens), LOOK.reach * 0.02, "a small cell: a share of its own size");
  finish.dispose();
});

test("the stage draws the picture as before and lays the passes over it; a view that asks for nothing changes nothing", () => {
  const calls = [];
  const renderer = { toneMapping: THREE.NoToneMapping, toneMappingExposure: 1, info: { autoReset: true, reset: () => calls.push("count afresh") }, render: () => calls.push("picture") };
  const stage = { look: new Look(), numbers: lookNumbers(), renderer, finish: null, fit: {}, scene: {}, camera: {}, width: 640, height: 400, invalidate: () => {} };
  stage.applyLook = Stage.prototype.applyLook;
  stage.look.onChange(() => stage.applyLook()); // as the stage itself listens
  const dress = (fit) => Stage.prototype.dress.call(stage, fit);
  const draw = () => {
    calls.length = 0;
    Stage.prototype.draw.call(stage);
    return calls.join(", ");
  };
  // A view that never asks: no passes are even made, and the renderer is left as it was.
  dress({ rich: false });
  assert.equal(stage.finish, null);
  assert.equal(renderer.toneMapping, THREE.NoToneMapping);
  assert.equal(renderer.toneMappingExposure, 1);
  assert.deepEqual(Object.values(stage.numbers).map((item) => item.value), [0, 0, 0, 0, 0]);
  assert.equal(draw(), "picture", "one picture, drawn as it always was");
  // The Cell view asks.
  dress({ rich: true, filmic: true, exposure: 1.08, contact: true, reach: 0.4, shade: 0.6 });
  assert.equal(renderer.toneMapping, THREE.NeutralToneMapping, "filmic light is three.js's neutral curve");
  assert.equal(renderer.toneMappingExposure, 1.08);
  assert.deepEqual([stage.numbers.translucency.value, stage.numbers.texture.value, stage.numbers.shimmer.value, stage.numbers.drift.value], [1, 1, 1, 1]);
  assert.deepEqual([stage.finish.contact.size, stage.finish.contact.reach, stage.finish.contact.strength], [1, 0.4, 0.6]);
  stage.finish.before = () => calls.push("contact shade worked out");
  stage.finish.after = () => calls.push("laid over");
  assert.equal(draw(), "count afresh, contact shade worked out, picture, laid over", "the picture itself is still drawn straight to the screen, between the two");
  assert.equal(renderer.info.autoReset, true);
  // Status colours: filmic light is left out, the rest stays.
  dress({ rich: true, filmic: false, exposure: 1.08, contact: true, reach: 0.4, shade: 0.6 });
  assert.equal(renderer.toneMapping, THREE.NoToneMapping);
  assert.equal(renderer.toneMappingExposure, 1);
  assert.equal(stage.finish.contact.size, 1);
  // Nothing solid near: no contact shade is worked out, and the picture is drawn alone again.
  dress({ rich: true, contact: false });
  assert.equal(stage.finish.active, false);
  assert.equal(draw(), "picture");
  // A device that cannot keep up: half size, then off.
  dress({ rich: true, contact: true, reach: 0.4 });
  frames(stage.look, 60);
  assert.equal(stage.finish.contact.size, 0.5);
  frames(stage.look, 60);
  assert.equal(stage.finish.active, false);
  frames(stage.look, 60);
  assert.deepEqual([stage.numbers.translucency.value, stage.numbers.texture.value, stage.numbers.shimmer.value, stage.numbers.drift.value], [0, 0, 0, 0]);
  assert.equal(renderer.toneMapping, THREE.NeutralToneMapping, "filmic light costs nothing in a frame: it stays");
  // The view left: all is as it was found.
  dress({ rich: false });
  assert.equal(renderer.toneMapping, THREE.NoToneMapping);
  assert.equal(renderer.toneMappingExposure, 1);
  assert.equal(stage.finish.active, false);
  // Bloom, for flux: off at rest; on, the passes run even where there is no contact shade.
  Stage.prototype.setBloom.call(stage, 0.6);
  assert.equal(stage.finish.bloom.strength, 0.6);
  assert.equal(draw(), "count afresh, contact shade worked out, picture, laid over");
  Stage.prototype.setBloom.call(stage, 0);
  assert.equal(draw(), "picture");
});

test("a texture fades away before it could break up into speckle, and each texture is gentle", () => {
  const source = read("src/core/materials.js");
  assert.match(source, /lookFoot = length\(fwidth\(vLookPos\)\);/, "how much of the part a pixel covers is measured once for each pixel");
  assert.match(source, /float lookFade\(float size\) \{ return 1\.0 - smoothstep\(0\.25 \* size, 0\.6 \* size, lookFoot\); \}/);
  const heights = [...source.matchAll(/float lookHeight\(vec3 p\) \{([^]*?)\n#(?:elif|else|endif)/g)].map((match) => match[1]);
  assert.equal(heights.length, 4, "grain, folds, pores, and none");
  for (const height of heights.slice(0, 3)) assert.match(height, /lookFade\(/, "every texture fades with distance");
  // How far each stands out, in micrometres of a cell twenty across: a few hundredths at most.
  const depths = heights.slice(0, 3).map((height) => Number(/return -?(0\.[0-9]+) \*/.exec(height)[1]));
  for (const depth of depths) assert.ok(depth >= 0.02 && depth <= 0.04, `a relief of ${depth}`);
  assert.match(source, /diffuseColor\.rgb \*= 1\.0 \+ uLookTexture \* 2\.0 \* \(lookHeight\(vLookPos\) - LOOK_LEVEL\);/, "and its tint is a few parts in a hundred");
});

test("the build bundles three.js's own passes into the page and adds no host", async () => {
  const { buildPage } = await import("../tools/lib/build_page.mjs");
  const page = await buildPage({});
  const hosts = [...new Set([...page.matchAll(/^import [^;]* from "(https?:\/\/[^"/]+)/gm)].map((match) => match[1]))];
  assert.deepEqual(hosts, ["https://cdnjs.cloudflare.com"], "three.js alone is loaded, from the host the page already used");
  assert.ok(!/from "three\//.test(page), "the add-ons are inside the page, not fetched");
  for (const piece of ["GTAOShader", "PoissonDenoiseShader", "LuminosityHighPassShader"]) assert.ok(page.includes(piece), `${piece} is in the page`);
  assert.ok(!/EffectComposer|OutputPass|RenderPass\b/.test(page), "no more of the add-ons than the two passes need");
});

/** A stand-in for the renderer that keeps what it is asked to do, for the passes' own order of work. */
function recorder() {
  const log = [];
  const renderer = {
    log,
    autoClear: true,
    shadowMap: { autoUpdate: true },
    clearColor: new THREE.Color(0x123456),
    clearAlpha: 0,
    target: null,
    getClearColor(into) {
      return into.copy(this.clearColor);
    },
    getClearAlpha() {
      return this.clearAlpha;
    },
    setClearColor(colour, alpha) {
      this.clearColor.set(colour);
      if (alpha !== undefined) this.clearAlpha = alpha;
    },
    setClearAlpha(alpha) {
      this.clearAlpha = alpha;
    },
    setRenderTarget(target) {
      this.target = target;
    },
    clear() {},
    render(scene, camera) {
      log.push({ target: this.target, scene, layers: camera.layers?.mask, during: renderer.during?.() });
    },
  };
  return renderer;
}

test("the extra pictures swap materials only for the while, and leave the scene and the renderer as they were", () => {
  const renderer = recorder();
  const finish = new Finish(renderer);
  const scene = new THREE.Scene(), camera = new THREE.PerspectiveCamera(34, 1, 0.1, 100);
  const shape = new THREE.BoxGeometry(1, 1, 1);
  const part = (options, data = {}) => Object.assign(new THREE.MeshStandardMaterial(options), { userData: { solidDepth: options.depthWrite ?? true, ...data } });
  const cut = [new THREE.Plane(new THREE.Vector3(0, -1, 0), 1)];
  const solidPart = new THREE.Mesh(shape, part({}));
  const cutPart = new THREE.Mesh(shape, Object.assign(part({ side: THREE.DoubleSide }), { clippingPlanes: cut }));
  const glass = new THREE.Mesh(shape, part({ transparent: true, opacity: 0.4, depthWrite: false }));
  const crowd = new THREE.Mesh(shape, part({}, { noContact: true }));
  const dots = new THREE.Points(shape, new THREE.PointsMaterial());
  const hidden = new THREE.Mesh(shape, part({}));
  hidden.visible = false;
  // A mark that carries data says itself that it stays out (core/look.js): an opaque thing that does not say so counts as a solid part.
  const bead = new THREE.Mesh(shape, Object.assign(new THREE.MeshBasicMaterial({ color: 0xffcc00 }), { userData: { noContact: true } }));
  scene.add(solidPart, cutPart, glass, crowd, dots, hidden, bead);
  const own = [solidPart, cutPart, glass, crowd, dots, hidden, bead].map((object) => object.material);
  const mask = camera.layers.mask;
  const drawn = (layer) => [solidPart, cutPart, glass, crowd, dots, hidden, bead].map((object) => object.layers.isEnabled(layer));

  // Contact shade's picture: the solid parts alone, each as its facing, cut where its own material is cut.
  renderer.during = () => ({ materials: [solidPart.material, cutPart.material], shown: drawn(29), auto: renderer.autoClear, shadows: renderer.shadowMap.autoUpdate, clear: renderer.clearColor.getHex() });
  const picture = {};
  finish.redraw(scene, camera, picture, 29, (object) => (object.isMesh && solid(object.material) ? finish.facing.for(object.material) : null), 0x7777ff, 1);
  const first = renderer.log.at(-1);
  assert.equal(first.target, picture);
  assert.equal(first.layers, 1 << 29, "the camera looks at that picture's layer alone");
  assert.deepEqual(first.during.shown, [true, true, false, false, false, false, false], "solid parts only: no glass, no drifting crowd, no dots, nothing hidden, no mark that says it stays out");
  assert.ok(first.during.materials.every((material) => material.isMeshNormalMaterial), "each drawn as its facing");
  assert.equal(first.during.materials[1].clippingPlanes, cut, "a part cut open is cut in this picture too");
  assert.equal(first.during.materials[1].side, THREE.DoubleSide);
  assert.notEqual(first.during.materials[0], first.during.materials[1], "a cut part and an uncut one do not share a stand-in");
  assert.equal(first.during.clear, 0x7777ff);
  assert.equal(first.during.shadows, false, "the scene's shadows are not worked out again for it");
  // Afterwards all is as it was.
  assert.deepEqual([solidPart, cutPart, glass, crowd, dots, hidden, bead].map((object) => object.material), own, "every part has its own material back");
  assert.equal(camera.layers.mask, mask);
  assert.equal(renderer.autoClear, true);
  assert.equal(renderer.shadowMap.autoUpdate, true);
  assert.equal(renderer.clearColor.getHex(), 0x123456);
  assert.equal(renderer.clearAlpha, 0);

  // The glow's picture: what was marked, as itself; solid parts in front of it, black; nothing else.
  finish.glow(bead);
  renderer.during = () => ({ materials: [solidPart.material, bead.material], shown: drawn(30) });
  finish.redraw(scene, camera, picture, 30, (object) => (finish.shines(object) ? true : object.isMesh && solid(object.material) ? finish.dark.for(object.material) : null), 0x000000, 0);
  const second = renderer.log.at(-1);
  assert.deepEqual(second.during.shown, [true, true, false, false, false, false, true], "the marked thing and the solid parts that may hide it");
  assert.ok(second.during.materials[0].isMeshBasicMaterial && second.during.materials[0].color.getHex() === 0, "a solid part hides the glow behind it, and gives none");
  assert.equal(second.during.materials[1], own[6], "the marked thing shines as itself");
  assert.deepEqual([solidPart, cutPart, glass, crowd, dots, hidden, bead].map((object) => object.material), own);
});

test("a frame with the passes: contact shade is worked out first, then laid over the picture at its strength; bloom only for what is marked", () => {
  const renderer = recorder();
  const finish = new Finish(renderer);
  const scene = new THREE.Scene(), camera = new THREE.PerspectiveCamera(34, 4 / 3, 0.1, 100);
  scene.add(new THREE.Mesh(new THREE.BoxGeometry(1, 1, 1), Object.assign(new THREE.MeshStandardMaterial(), { userData: { solidDepth: true } })));
  finish.setSize(640, 480);
  finish.setContact(1, { reach: 0.5, strength: 0.65 });
  finish.before(scene, camera);
  const pass = finish.contact.pass;
  assert.deepEqual(renderer.log.map((entry) => entry.target), [finish.contact.picture, pass.gtaoRenderTarget, pass.pdRenderTarget], "the solid parts' picture, the shade from it, the shade smoothed");
  assert.equal(renderer.target, null, "and the renderer is handed back looking at the screen");
  renderer.log.length = 0;
  finish.after();
  assert.equal(renderer.log.length, 1, "one more pass lays the shade over the picture");
  assert.equal(renderer.log[0].target, null);
  assert.equal(pass.blendMaterial.uniforms.intensity.value, 0.65);
  assert.equal(pass.blendMaterial.uniforms.tDiffuse.value, pass.pdRenderTarget.texture);
  assert.equal(pass.blendMaterial.blendSrc, THREE.DstColorFactor, "the picture times the shade");
  assert.equal(pass.blendMaterial.blendSrcAlpha, THREE.DstAlphaFactor, "its cover kept");
  assert.equal(renderer.autoClear, true);
  // Bloom switched on with nothing marked: no pass runs for it.
  finish.setBloom(0.6);
  renderer.log.length = 0;
  finish.before(scene, camera);
  assert.equal(renderer.log.length, 3, "nothing marked: nothing more is drawn");
  // Something marked: its picture, the blurs, and one pass that adds the glow.
  const bead = new THREE.Mesh(new THREE.SphereGeometry(0.1), new THREE.MeshBasicMaterial({ color: 0xffcc00 }));
  scene.add(bead);
  finish.glow(bead);
  renderer.log.length = 0;
  finish.before(scene, camera);
  assert.equal(renderer.log[3].target, finish.bloom.picture, "what was marked, in a picture of its own");
  assert.ok(renderer.log.length > 4 + 10, "then the high pass and five blurs each way");
  assert.equal(finish.bloom.pass.strength, 0.6);
  renderer.log.length = 0;
  finish.after();
  assert.equal(renderer.log.length, 2, "the shade, then the glow");
  assert.equal(finish.add.material.uniforms.tDiffuse.value, finish.bloom.pass.renderTargetsHorizontal[0].texture);
  assert.equal(finish.add.material.blendDst, THREE.OneFactor, "added as light");
  // Contact shade off (a device that gave it up) while flux glows: only the glow's passes run.
  finish.setContact(0);
  renderer.log.length = 0;
  finish.before(scene, camera);
  assert.equal(renderer.log[0].target, finish.bloom.picture);
  finish.setBloom(0);
  assert.equal(finish.active, false);
  finish.dispose();
});
