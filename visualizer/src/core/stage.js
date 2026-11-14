// The stage: one renderer, camera and light rig shared by every lens. It draws only
// when something changed or a lens is animating, and it owns picking.

import * as THREE from "../three.js";
import { OrbitRig } from "./controls.js";
import { readPalette, watchTheme } from "./theme.js";

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
    this.reducedMotion = matchMedia("(prefers-reduced-motion: reduce)").matches;
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

  /** A lens registers a tick(dt, time) that returns true while it is animating. */
  onTick(callback) {
    this.listeners.add(callback);
    return () => this.listeners.delete(callback);
  }

  frame(time) {
    const dt = Math.min(100, time - this.last);
    this.last = time;
    let animating = this.rig.update(dt);
    if (document.visibilityState === "visible") {
      for (const tick of this.listeners) animating = tick(dt, time) || animating;
    }
    if (this.needsRender || animating) {
      this.renderer.render(this.scene, this.camera);
      for (const callback of this.afterRender) callback();
      this.needsRender = false;
    }
    if (animating && document.visibilityState === "visible") {
      requestAnimationFrame((next) => this.frame(next));
    } else {
      this.running = false;
    }
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
    for (const hit of hits) {
      // pickFilter lets a shape ignore hits on parts of it that are clipped away.
      if (hit.object.userData.pickFilter && !hit.object.userData.pickFilter(hit)) continue;
      let id = null, shown = true, passThrough = false, blocker = false;
      for (let node = hit.object; node; node = node.parent) {
        if (!node.visible) shown = false;
        if (node.userData.unpickable) passThrough = true;
        if (node.userData.blocker) blocker = true;
        if (id === null && node.userData.pick) id = node.userData.pick;
      }
      if (!shown || passThrough) continue; // hidden things and illustrations do not stop a click
      if (blocker) return null; // a solid surface such as a plate does
      if (id) return { id, object: hit.object, point: hit.point };
    }
    return null;
  }

  /** Project a world point to pixel coordinates; z > 1 means behind the camera or beyond. */
  project(point, out) {
    out.copy(point).project(this.camera);
    out.x = (out.x * 0.5 + 0.5) * this.width;
    out.y = (-out.y * 0.5 + 0.5) * this.height;
    return out;
  }

  dispose() {
    this.stopWatching();
    this.observer.disconnect();
    document.removeEventListener("visibilitychange", this.onVisibility);
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
