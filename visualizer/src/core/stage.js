// The stage: one renderer, camera and light rig shared by every lens. It draws only
// when something changed or a lens is animating, and it owns picking.

import * as THREE from "../three.js";
import { OrbitRig } from "./controls.js";
import { readPalette, watchTheme } from "./theme.js";
import { Look, Decoration } from "./look.js";
import { Finish } from "./passes.js";
import { lookNumbers } from "./materials.js";

// What a view that asks for nothing gets of the look at rest: nothing (see dress()).
const FIT = { rich: false, filmic: true, exposure: 1.08, contact: true, reach: 1, shade: 0.6 };

/** A gap between two frames longer than this, in milliseconds, is no frame but a pause: the window was hidden, the machine slept. */
export const PAUSE_MS = 2000;

/**
 * The two times of a frame, from the gap since the frame before, in milliseconds. `dt` is a
 * step for what glides (the camera, a look that settles): never more than a tenth of a
 * second, so that a hitch is no jump. `real` is the time that really passed, for what keeps a
 * stated clock (a replay's playhead says its speed): the long frames of a slow device count
 * in full, up to two seconds. A longer gap is a pause and counts as one step, as it always
 * did. (Half a second was tried first: the checks' own browser, which draws in software and
 * at times leaves more than half a second between frames, then ran a replay at a fifth of
 * the speed it stated.)
 */
export function frameTimes(gap) {
  const passed = Math.max(0, gap), dt = Math.min(100, passed);
  return { dt, real: passed > PAUSE_MS ? dt : passed };
}

export class Stage {
  constructor({ canvas, host }) {
    this.canvas = canvas;
    this.host = host;
    this.renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true, powerPreference: "high-performance" });
    this.renderer.setClearColor(0x000000, 0);
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;
    this.renderer.toneMapping = THREE.NoToneMapping;
    this.renderer.localClippingEnabled = true;
    this.renderer.shadowMap.enabled = true;
    this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;

    this.scene = new THREE.Scene();
    this.camera = new THREE.PerspectiveCamera(34, 1, 0.1, 5000);
    this.rig = new OrbitRig(this.camera, canvas, () => this.invalidate());

    this.sky = new THREE.HemisphereLight(0xffffff, 0x8899aa, 2.1);
    this.sun = new THREE.DirectionalLight(0xffffff, 1.5);
    this.sun.position.set(40, 90, 55);
    this.sun.castShadow = true;
    this.sun.shadow.mapSize.set(2048, 2048);
    this.sun.shadow.bias = -0.0006;
    this.sun.shadow.normalBias = 0.05;
    this.scene.add(this.sky, this.sun, this.sun.target);

    this.raycaster = new THREE.Raycaster();
    this.pointer = new THREE.Vector2();
    this.listeners = new Set();
    this.afterRender = new Set();
    this.paletteListeners = new Set();
    this.palette = readPalette(host);
    this.motion = matchMedia("(prefers-reduced-motion: reduce)");
    this.reducedMotion = this.motion.matches;
    // The look at rest (core/look.js): which effects are drawn, the clock of what moves only for
    // decoration, the numbers every enriched material shares, and what the view shown asks for.
    this.look = new Look();
    this.decoration = new Decoration({ still: this.reducedMotion });
    this.numbers = lookNumbers();
    this.fit = { ...FIT };
    this.finish = null; // the finishing passes (core/passes.js), made when first asked for
    this.moving = false;
    this.look.onChange(() => this.applyLook());
    // A visitor may ask for less motion while the page is open: what the page says of the look follows.
    this.onMotion = () => {
      this.reducedMotion = this.decoration.still = this.motion.matches;
      this.look.changed();
    };
    this.motion.addEventListener("change", this.onMotion);
    this.width = 1;
    this.height = 1;
    this.needsRender = true;
    this.running = false;
    this.last = 0;

    this.stopWatching = watchTheme(() => this.refreshPalette());
    this.observer = new ResizeObserver(() => this.resize());
    this.observer.observe(host);
    this.onVisibility = () => this.invalidate();
    document.addEventListener("visibilitychange", this.onVisibility);
    // A lost context that has come back: three.js sets itself up again and core/environment.js makes its
    // surroundings again, each in its own listener; the picture is then drawn again.
    this.onRestored = () => this.invalidate();
    canvas.addEventListener("webglcontextrestored", this.onRestored);
    this.resize();
    this.applyPalette();
  }

  // ------------------------------------------------------------ drawing

  /** Ask for a frame. Cheap to call often. */
  invalidate() {
    this.needsRender = true;
    if (!this.running) {
      this.running = true;
      this.last = performance.now();
      requestAnimationFrame((time) => this.frame(time));
    }
  }

  /**
   * "frames=1" in the address: a small readout at the foot of the picture of the frames this
   * device really draws, as the mean time between the frames drawn in the last second and the
   * frames a second that makes. The server that checks the page draws in software, so the figure
   * that counts is the one read on the visitor's own device. Absent, nothing is shown and
   * nothing is measured. It only watches frames as they are drawn: it asks for none, and the
   * clock the views keep (frameTimes) is not touched.
   */
  showFrames(parent) {
    if (this.frames) return;
    const box = document.createElement("div");
    box.className = "frame-readout";
    box.setAttribute("role", "status");
    Object.assign(box.style, { position: "absolute", left: "max(16px, env(safe-area-inset-left, 0px))", bottom: "4px", zIndex: "6", padding: "1px 6px", borderRadius: "6px", border: "1px solid var(--line)", background: "var(--bg-raised)", color: "var(--muted)", font: "11px/1.3 var(--font-body, system-ui, sans-serif)", fontVariantNumeric: "tabular-nums", pointerEvents: "none" });
    (parent || this.canvas.parentNode || this.host).append(box);
    const drawn = [];
    const watch = () => drawn.push(performance.now());
    const write = () => {
      const now = performance.now();
      // The frames of the last second; where a frame takes longer than that, the last two. It says
      // what was measured: a picture that stands and a device that stalls both draw no frame.
      while (drawn.length > 2 && drawn[0] < now - 1000) drawn.shift();
      if (drawn.length < 2) box.textContent = "Frames: fewer than two drawn yet";
      else if (drawn.at(-1) < now - 4000) box.textContent = "Frames: none drawn in the last 4 seconds";
      else {
        const mean = (drawn.at(-1) - drawn[0]) / (drawn.length - 1);
        box.textContent = `Frames: ${mean.toFixed(1)} ms · ${(1000 / mean).toFixed(mean > 100 ? 1 : 0)} a second, over the last ${mean > 1000 ? "two frames" : "second"}`;
      }
    };
    this.afterRender.add(watch);
    const timer = setInterval(write, 500);
    write();
    this.frames = { box, stop: () => (this.afterRender.delete(watch), clearInterval(timer), box.remove()) };
  }

  /** A lens registers a tick(dt, time, real) that returns true while it is animating (frameTimes says what dt and real are). */
  onTick(callback) {
    this.listeners.add(callback);
    return () => this.listeners.delete(callback);
  }

  frame(time) {
    // A frame's timestamp can be a little earlier than the clock read when it was asked for.
    const { dt, real } = frameTimes(time - this.last);
    this.last = time;
    let animating = this.rig.update(dt);
    if (document.visibilityState === "visible") {
      for (const tick of this.listeners) animating = tick(dt, time, real) || animating;
    }
    // What moves for decoration only keeps no frame coming by itself: it moves while a view does.
    if (animating && this.decoration.tick(dt)) this.numbers.time.value = this.decoration.time;
    if (this.needsRender || animating) {
      this.draw();
      for (const callback of this.afterRender) callback();
      this.needsRender = false;
      // A device that cannot keep a moving picture smooth gives up part of the rich look.
      if (animating && this.moving) this.look.frame(dt);
    }
    this.moving = animating;
    if (animating && document.visibilityState === "visible") {
      requestAnimationFrame((next) => this.frame(next));
    } else {
      this.running = false;
    }
  }

  /** One picture: the scene as it always was drawn, with the finishing passes over it where a view asked for them. */
  draw() {
    const finish = this.finish?.active ? this.finish : null;
    if (!finish) {
      this.renderer.render(this.scene, this.camera);
      return;
    }
    // The counts of what was drawn are then of the whole frame, not of its last pass.
    const info = this.renderer.info;
    info.autoReset = false;
    info.reset();
    finish.setSize(this.width, this.height);
    finish.before(this.scene, this.camera);
    this.renderer.render(this.scene, this.camera);
    finish.after();
    info.autoReset = true;
  }

  // ------------------------------------------------------------ the look at rest

  /**
   * A view asks for the rich look while it is shown, and says what of it fits now:
   *   rich      whether it wants the look at all (a view that never asks keeps the look it had);
   *   filmic    false while its colours carry a meaning (status colours): those stay as their legend shows them;
   *   exposure  how much light filmic light lets in: a little over 1 keeps the middle tones where they were;
   *   contact   false while nothing solid is near enough for contact shade to show;
   *   reach     how far one part closes another in, in the scene's units; shade  how dark, 0 to 1.
   */
  dress(fit = {}) {
    this.fit = { ...FIT, ...fit };
    this.look.want(this.fit.rich);
    this.applyLook();
  }

  /** Bring the renderer, the shared numbers and the passes in line with the look as it now is. */
  applyLook() {
    const { look, fit, numbers } = this;
    numbers.translucency.value = look.on("translucency") ? 1 : 0;
    numbers.texture.value = look.on("texture") ? 1 : 0;
    numbers.shimmer.value = look.on("shimmer") ? 1 : 0;
    numbers.drift.value = look.on("drift") ? 1 : 0;
    // Filmic light: highlights roll off instead of clipping (three.js's "neutral" curve, the
    // Khronos one made to keep colours true). A mark whose colour carries a meaning stays out
    // of it by its own material (toneMapped false).
    const filmic = look.on("filmic") && fit.filmic;
    this.renderer.toneMapping = filmic ? THREE.NeutralToneMapping : THREE.NoToneMapping;
    this.renderer.toneMappingExposure = filmic ? fit.exposure : 1;
    const size = fit.contact ? look.contact : 0;
    if (size > 0 || this.finish) {
      this.finish ??= new Finish(this.renderer);
      this.finish.setContact(size, { reach: fit.reach, strength: fit.shade });
    }
    this.invalidate();
  }

  /**
   * Bloom, for flux: on at this strength, off at 0. Only what was marked with glow() shines.
   * `radius` is how wide the glow spreads (0 to 1); `floor` how bright a marked thing must be.
   */
  setBloom(strength = 0, options = {}) {
    if (!(strength > 0) && !this.finish) return;
    this.finish ??= new Finish(this.renderer);
    this.finish.setBloom(strength, options);
    this.invalidate();
  }

  /** Mark an object, with all it holds, as something the bloom shines from; glow(object, false) unmarks it. */
  glow(object, on = true) {
    this.finish ??= new Finish(this.renderer);
    this.finish.glow(object, on);
    this.invalidate();
  }

  resize() {
    const width = this.host.clientWidth;
    const height = this.host.clientHeight;
    if (!width || !height) return;
    this.width = width;
    this.height = height;
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    this.renderer.setSize(width, height, false);
    this.camera.aspect = width / height;
    // A tall, narrow screen needs a wider field of view to keep the subject in frame.
    this.camera.fov = width < height ? 46 : 34;
    this.applyInsets();
    this.invalidate();
  }

  /** Pixels covered by panels on the right and bottom; the view shifts to stay centred beside them. */
  setInsets({ right = 0, bottom = 0 } = {}) {
    this.insets = { right, bottom };
    this.applyInsets();
    this.invalidate();
  }

  applyInsets() {
    const { right = 0, bottom = 0 } = this.insets || {};
    if (right || bottom) this.camera.setViewOffset(this.width, this.height, right / 2, bottom / 2, this.width, this.height);
    else this.camera.clearViewOffset();
    this.camera.updateProjectionMatrix();
  }

  // ------------------------------------------------------------ theme

  onPalette(callback) {
    this.paletteListeners.add(callback);
    return () => this.paletteListeners.delete(callback);
  }

  refreshPalette() {
    const next = readPalette(this.host);
    if (JSON.stringify(next) === JSON.stringify(this.palette)) return;
    this.palette = next;
    this.applyPalette();
    for (const callback of this.paletteListeners) callback(next);
    this.invalidate();
  }

  applyPalette() {
    this.sky.intensity = this.palette.dark ? 1.5 : 2.1;
    this.sky.groundColor.set(this.palette.dark ? 0x1b2a3a : 0x9fb0c0);
    this.sun.intensity = this.palette.dark ? 1.9 : 1.5;
  }

  // ------------------------------------------------------------ picking

  /** The nearest pickable object under a client point, among the given roots. */
  pick(clientX, clientY, roots) {
    const rect = this.canvas.getBoundingClientRect();
    this.pointer.set(((clientX - rect.left) / rect.width) * 2 - 1, -((clientY - rect.top) / rect.height) * 2 + 1);
    this.raycaster.setFromCamera(this.pointer, this.camera);
    const hits = this.raycaster.intersectObjects(roots, true);
    let sketch = null;
    for (const hit of hits) {
      // pickFilter lets a shape ignore hits on parts of it that are clipped away.
      if (hit.object.userData.pickFilter && !hit.object.userData.pickFilter(hit)) continue;
      let id = null, shown = true, passThrough = false, blocker = false, seeThrough = false;
      for (let node = hit.object; node; node = node.parent) {
        if (!node.visible) shown = false;
        if (node.userData.unpickable) passThrough = true;
        if (node.userData.blocker) blocker = true;
        if (node.userData.seeThrough) seeThrough = true;
        // One mesh may hold many parts: its pick is then a function of what was hit.
        if (id === null && node.userData.pick) id = typeof node.userData.pick === "function" ? node.userData.pick(hit) : node.userData.pick;
      }
      if (!shown || passThrough) continue; // hidden things and illustrations do not stop a click
      if (blocker) break; // a solid surface such as a plate does
      if (!id) continue;
      if (seeThrough) {
        // A sketched part is picked only if nothing solid is seen through it.
        sketch ??= { id, object: hit.object, point: hit.point };
        continue;
      }
      return { id, object: hit.object, point: hit.point };
    }
    return sketch;
  }

  /** Project a world point to pixel coordinates; z > 1 means behind the camera or beyond. */
  project(point, out) {
    out.copy(point).project(this.camera);
    out.x = (out.x * 0.5 + 0.5) * this.width;
    out.y = (-out.y * 0.5 + 0.5) * this.height;
    return out;
  }

  dispose() {
    this.frames?.stop();
    this.stopWatching();
    this.observer.disconnect();
    document.removeEventListener("visibilitychange", this.onVisibility);
    this.canvas.removeEventListener("webglcontextrestored", this.onRestored);
    this.motion.removeEventListener("change", this.onMotion);
    this.finish?.dispose();
    this.rig.dispose();
    this.renderer.dispose();
  }
}

/** Free the GPU resources of a lens's objects. */
export function disposeTree(root) {
  root.traverse((object) => {
    object.geometry?.dispose?.();
    const materials = Array.isArray(object.material) ? object.material : object.material ? [object.material] : [];
    for (const material of materials) {
      material.map?.dispose?.();
      material.dispose?.();
    }
  });
}
