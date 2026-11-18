// The finishing passes: contact shade, and bloom for flux. They are laid over the picture
// the renderer has just drawn; the picture itself is drawn straight to the screen exactly
// as before, so glass blends as it always did and the screen's own smoothing of edges
// stays. A view that asks for neither pays nothing: nothing here runs.
//
// Both use three.js's own add-on modules (MIT, three.js r170, examples/jsm), bundled into
// the page by the build:
//   GTAOPass         ground-truth ambient occlusion, with its Poisson denoise
//   UnrealBloomPass  a chain of blurs at falling sizes
//
// Contact shade: the solid parts are drawn once more, small, as their facing and their
// depth; from that the pass works out how closed in each point is; and the result is
// multiplied onto the screen. Glass takes no part: only what is solid darkens and is
// darkened. A part that is cut open is cut here too, by its own material's cut.
//
// Bloom: what was marked with glow() is drawn once more, on black, where no solid part lies in
// front of it; the pass blurs it; the blur is added onto the screen. So only what was marked
// shines, never the highlights of the scene, and never through a solid part. Off unless asked
// for. Where contact shade is on, its picture already holds the solid parts' depth, drawn by the
// same camera in the same frame: the marked things are drawn against that depth, and the solid
// parts are not drawn a second time (the cost of a frame with flux, 16 November 2026: that
// second drawing was about a fifth of the frame on the card). Without contact shade, the solid
// parts are drawn black in front of the marked things, as before.
// A marked thing is drawn there without the scene's lamps: an unlit material shines by its
// own colour, a lit one by the light it gives off itself and by its surroundings. How
// bright it is there is how much it glows; `floor` leaves out what is dimmer than that.

import * as THREE from "../three.js";
import { GTAOPass } from "three/addons/postprocessing/GTAOPass.js";
import { UnrealBloomPass } from "three/addons/postprocessing/UnrealBloomPass.js";
import { FullScreenQuad } from "three/addons/postprocessing/Pass.js";

// Layers used only while the extra pictures are drawn; no camera looks at them otherwise.
const SOLIDS = 29, GLOW = 30;
const NO_CUT = {}; // the key for materials that are not cut

/**
 * Whether a mesh's material is a solid surface now: one that takes part in contact shade
 * and hides a glow behind it. Glass, sketches, dots and lines do not; nor does a part
 * while it is faded or dimmed, or one that says it stays out (`userData.noContact`).
 */
export function solid(material) {
  if (!material || Array.isArray(material)) return false;
  if (material.visible === false || material.colorWrite === false || material.wireframe) return false;
  const data = material.userData || {};
  if (data.sketch || data.noContact) return false;
  const meant = data.solidDepth ?? material.depthWrite; // whether it was made to hide what lies behind it
  return Boolean(meant) && material.opacity >= 0.7;
}

/** One stand-in material for each cut, side and shading a solid part can have. */
class StandIns {
  constructor(make) {
    this.make = make;
    this.byCut = new WeakMap();
  }

  for(material) {
    const cut = material.clippingPlanes || NO_CUT;
    let found = this.byCut.get(cut);
    if (!found) this.byCut.set(cut, (found = new Map()));
    const key = `${material.side}|${material.flatShading ? 1 : 0}`;
    if (!found.has(key)) {
      const made = this.make();
      made.side = material.side;
      made.flatShading = Boolean(material.flatShading);
      made.clippingPlanes = material.clippingPlanes || null;
      found.set(key, made);
    }
    return found.get(key);
  }
}

export class Finish {
  constructor(renderer) {
    this.renderer = renderer;
    this.width = 1; // of the page, in its own pixels
    this.height = 1;
    // Contact shade. `size` is how many of the page's pixels one of its own stands for, each way
    // (1 or 0.5; 0 is off); `reach` is how far a part closes another in, in the scene's units,
    // and also how far behind a point a thing may lie and still shade it: what is farther is
    // another part in front, not a part touching. `strength` is how much of the shade is laid
    // over the picture (0 to 1), `power` how much the shade is deepened first (1 is as worked out).
    this.contact = { size: 0, strength: 0.6, reach: 1, power: 1, pass: null, picture: null, sized: "" };
    // Bloom. Off at 0. `radius` and `floor` are the pass's own: how wide the glow spreads,
    // and how bright a marked thing must be to shine at all.
    // `shared`: draw the marked things over the contact shade's depth where it is on (false draws the solid parts
    // again, the way it was before 16 November 2026; kept so that the two can be measured side by side).
    this.bloom = { strength: 0, radius: 0.55, floor: 0, pass: null, picture: null, sized: "", over: null, overFor: null, shared: true };
    this.sources = new Set();
    this.facing = new StandIns(() => new THREE.MeshNormalMaterial({ blending: THREE.NoBlending }));
    this.dark = new StandIns(() => new THREE.MeshBasicMaterial({ color: 0x000000, toneMapped: false }));
    this.swapped = [];
    this.clear = new THREE.Color();
    this.ready = { contact: false, bloom: false };
  }

  get active() {
    return this.contact.size > 0 || this.bloom.strength > 0;
  }

  setSize(width, height) {
    this.width = Math.max(1, Math.round(width));
    this.height = Math.max(1, Math.round(height));
  }

  /** Contact shade at this size (1, 0.5, or 0 for off), reaching this far in the scene's units. */
  setContact(size, { reach, strength, power } = {}) {
    this.contact.size = size > 0 ? size : 0;
    if (reach !== undefined) this.contact.reach = reach;
    if (strength !== undefined) this.contact.strength = strength;
    if (power !== undefined) this.contact.power = power;
  }

  /** Bloom at this strength; 0 switches it off. */
  setBloom(strength, { radius, floor } = {}) {
    this.bloom.strength = strength > 0 ? strength : 0;
    if (radius !== undefined) this.bloom.radius = radius;
    if (floor !== undefined) this.bloom.floor = floor;
  }

  /** Mark an object, with all it holds, as something the bloom shines from; or unmark it. */
  glow(object, on = true) {
    if (on) this.sources.add(object);
    else this.sources.delete(object);
  }

  // ------------------------------------------------------------ the extra pictures

  /**
   * Draw the scene once more into `picture`, each visible thing as `as(object)` says: a
   * material to stand in for its own, true for its own, or null to leave it out. With
   * `keepDepth` the picture's depth is kept as it is (only its colour is cleared), so that
   * what is drawn is hidden where a depth already there lies in front of it.
   */
  redraw(scene, camera, picture, layer, as, colour, alpha, keepDepth = false) {
    const { renderer, swapped } = this;
    swapped.length = 0;
    scene.traverseVisible((object) => {
      if (!(object.isMesh || object.isPoints || object.isLine || object.isSprite)) return;
      const stand = as(object);
      if (!stand) {
        object.layers.disable(layer);
        return;
      }
      object.layers.enable(layer);
      if (stand !== true) {
        swapped.push(object, object.material);
        object.material = stand;
      }
    });
    const mask = camera.layers.mask, auto = renderer.autoClear, shadows = renderer.shadowMap.autoUpdate;
    renderer.getClearColor(this.clear);
    const clearAlpha = renderer.getClearAlpha();
    camera.layers.set(layer);
    renderer.shadowMap.autoUpdate = false;
    renderer.setRenderTarget(picture);
    renderer.setClearColor(colour, alpha);
    if (keepDepth) {
      renderer.autoClear = false;
      renderer.clear(true, false, false);
    } else renderer.autoClear = true;
    renderer.render(scene, camera);
    renderer.autoClear = auto;
    renderer.setClearColor(this.clear, clearAlpha);
    renderer.shadowMap.autoUpdate = shadows;
    camera.layers.mask = mask;
    for (let index = 0; index < swapped.length; index += 2) swapped[index].material = swapped[index + 1];
    swapped.length = 0;
  }

  contactPass(scene, camera) {
    const contact = this.contact;
    const width = Math.max(2, Math.round(this.width * contact.size)), height = Math.max(2, Math.round(this.height * contact.size));
    if (!contact.pass) {
      const depth = new THREE.DepthTexture(width, height);
      depth.format = THREE.DepthStencilFormat;
      depth.type = THREE.UnsignedInt248Type;
      contact.picture = new THREE.WebGLRenderTarget(width, height, { minFilter: THREE.NearestFilter, magFilter: THREE.NearestFilter, type: THREE.HalfFloatType, depthTexture: depth });
      contact.pass = new GTAOPass(scene, camera, width, height);
      contact.pass.setGBuffer(depth, contact.picture.texture); // facing and depth come from the picture drawn here
      contact.pass.output = GTAOPass.OUTPUT.Off; // it lays nothing over anything itself
      contact.pass.updateGtaoMaterial({ distanceExponent: 1.4, distanceFallOff: 1, samples: 12, screenSpaceRadius: false });
      contact.pass.updatePdMaterial({ lumaPhi: 10, normalPhi: 3, radius: 6, radiusExponent: 2, rings: 2, samples: 12 });
      contact.sized = "";
    }
    const sized = `${width}x${height}`;
    if (contact.sized !== sized) {
      contact.picture.setSize(width, height);
      contact.pass.setSize(width, height);
      contact.sized = sized;
    }
    contact.pass.scene = scene;
    contact.pass.camera = camera;
    // What follows the scene's scale is set for each frame: these are plain numbers to the pass, no new shader.
    contact.pass.updateGtaoMaterial({ radius: contact.reach, thickness: contact.reach, scale: contact.power });
    contact.pass.updatePdMaterial({ depthPhi: 2 * contact.reach }); // the smoothing stays on one surface
    return contact.pass;
  }

  /**
   * The picture the marked things are drawn into over the contact shade's depth: the contact
   * picture's size, its depth texture shared (nothing drawn here writes depth: the marks do
   * not, and the solid parts are not drawn). Made again when the contact picture changes.
   */
  overContact() {
    const bloom = this.bloom, contact = this.contact.picture;
    const key = contact ? `${contact.width}x${contact.height}` : null;
    if (bloom.over && bloom.overFor === contact && bloom.overKey === key) return bloom.over;
    bloom.over?.dispose();
    bloom.over = new THREE.WebGLRenderTarget(contact.width, contact.height, { type: THREE.HalfFloatType, depthBuffer: true, stencilBuffer: true, depthTexture: contact.depthTexture });
    bloom.overFor = contact;
    bloom.overKey = key;
    return bloom.over;
  }

  bloomPass(size = null) {
    const bloom = this.bloom;
    const width = Math.max(2, size ? size.width : this.width), height = Math.max(2, size ? size.height : this.height);
    if (!bloom.pass) {
      bloom.picture = new THREE.WebGLRenderTarget(width, height, { type: THREE.HalfFloatType });
      bloom.pass = new UnrealBloomPass(new THREE.Vector2(width, height), bloom.strength, bloom.radius, bloom.floor);
      // The blur alone is added onto the screen: as light, and as a little cover, so that it shows on a pale page too.
      this.add = new FullScreenQuad(
        new THREE.ShaderMaterial({
          uniforms: { tDiffuse: { value: null } },
          vertexShader: "varying vec2 vUv; void main() { vUv = uv; gl_Position = vec4(position.xy, 0.0, 1.0); }",
          fragmentShader: [
            "uniform sampler2D tDiffuse; varying vec2 vUv;",
            "void main() {",
            "  vec3 glow = texture2D(tDiffuse, vUv).rgb;",
            "  gl_FragColor = vec4(glow, clamp(dot(glow, vec3(0.2126, 0.7152, 0.0722)), 0.0, 1.0));",
            "  #include <colorspace_fragment>",
            "}",
          ].join("\n"),
          blending: THREE.CustomBlending,
          blendEquation: THREE.AddEquation,
          blendSrc: THREE.OneFactor,
          blendDst: THREE.OneFactor,
          blendSrcAlpha: THREE.OneFactor,
          blendDstAlpha: THREE.OneFactor,
          depthTest: false,
          depthWrite: false,
          transparent: true,
          toneMapped: false,
        })
      );
      bloom.sized = "";
    }
    const sized = `${width}x${height}`;
    if (bloom.sized !== sized) {
      bloom.picture.setSize(width, height);
      bloom.pass.setSize(width, height);
      bloom.sized = sized;
    }
    bloom.pass.strength = bloom.strength;
    bloom.pass.radius = bloom.radius;
    bloom.pass.threshold = bloom.floor;
    return bloom.pass;
  }

  /** Whether an object is, or stands under, something marked to glow. */
  shines(object) {
    for (let node = object; node; node = node.parent) if (this.sources.has(node)) return true;
    return false;
  }

  // ------------------------------------------------------------ a frame

  /** Before the picture is drawn: work out the contact shade and the glow, each in a picture of its own. */
  before(scene, camera) {
    const { renderer } = this;
    this.ready.contact = this.ready.bloom = false;
    if (this.contact.size > 0) {
      const pass = this.contactPass(scene, camera);
      this.redraw(scene, camera, this.contact.picture, SOLIDS, (object) => (object.isMesh && solid(object.material) ? this.facing.for(object.material) : null), 0x7777ff, 1);
      pass.render(renderer, null, null);
      this.ready.contact = true;
    }
    if (this.bloom.strength > 0 && this.sources.size) {
      if (this.ready.contact && this.bloom.shared) {
        // The solid parts' depth is in the contact picture: the marked things alone are drawn, against it.
        const over = this.overContact();
        const pass = this.bloomPass(over);
        this.redraw(scene, camera, over, GLOW, (object) => (this.shines(object) ? true : null), 0x000000, 0, true);
        pass.render(renderer, null, over, 0, false);
      } else {
        const pass = this.bloomPass();
        this.redraw(scene, camera, this.bloom.picture, GLOW, (object) => (this.shines(object) ? true : object.isMesh && solid(object.material) ? this.dark.for(object.material) : null), 0x000000, 0);
        pass.render(renderer, null, this.bloom.picture, 0, false);
      }
      this.ready.bloom = true;
    }
    renderer.setRenderTarget(null);
  }

  /** After the picture is drawn: lay the contact shade and the glow over it. */
  after() {
    const { renderer } = this;
    const auto = renderer.autoClear;
    renderer.setRenderTarget(null);
    renderer.autoClear = false;
    if (this.ready.contact) {
      const pass = this.contact.pass;
      // The pass's own way of laying its shade over a picture: the picture times the shade, its cover kept.
      pass.blendMaterial.uniforms.intensity.value = this.contact.strength;
      pass.blendMaterial.uniforms.tDiffuse.value = pass.pdRenderTarget.texture;
      pass.fsQuad.material = pass.blendMaterial;
      pass.fsQuad.render(renderer);
    }
    if (this.ready.bloom) {
      this.add.material.uniforms.tDiffuse.value = this.bloom.pass.renderTargetsHorizontal[0].texture;
      this.add.render(renderer);
    }
    renderer.autoClear = auto;
  }

  dispose() {
    this.contact.pass?.dispose();
    this.contact.picture?.dispose();
    this.contact.picture?.depthTexture?.dispose();
    this.bloom.pass?.dispose();
    this.bloom.picture?.dispose();
    this.bloom.over?.dispose();
    this.add?.material.dispose();
    this.add?.dispose();
  }
}
