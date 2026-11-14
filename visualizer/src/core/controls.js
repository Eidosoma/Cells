// Camera control written for this viewer: orbit, pan, zoom and animated flights.
// Distances are interpolated on a log scale, so one control works from a membrane
// patch to a whole organism.

import * as THREE from "../three.js";

const TWO_PI = Math.PI * 2;
const ease = (t) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);

export class OrbitRig {
  constructor(camera, element, onChange) {
    this.camera = camera;
    this.element = element;
    this.onChange = onChange;
    this.target = new THREE.Vector3();
    this.distance = 60;
    this.azimuth = 0.7;
    this.polar = 1.05;
    this.limits = { minDistance: 4, maxDistance: 400, minPolar: 0.12, maxPolar: Math.PI / 2 - 0.02 };
    this.velocity = { azimuth: 0, polar: 0 };
    this.flight = null;
    this.dragged = false;
    this.enabled = true;
    this.instant = false; // set for still pictures: flights arrive at once
    this.pointers = new Map();
    this.listen();
    this.apply();
  }

  // ------------------------------------------------------------ views

  view() {
    return { target: this.target.clone(), distance: this.distance, azimuth: this.azimuth, polar: this.polar };
  }

  setView(view) {
    this.flight = null;
    if (view.target) this.target.copy(view.target);
    if (view.distance !== undefined) this.distance = view.distance;
    if (view.azimuth !== undefined) this.azimuth = view.azimuth;
    if (view.polar !== undefined) this.polar = view.polar;
    this.velocity.azimuth = this.velocity.polar = 0;
    this.apply();
    this.onChange();
  }

  /** Animate to a view. With reduced motion, or when asked to be instant, the camera jumps there. */
  flyTo(view, milliseconds = 900) {
    if (this.instant || matchMedia("(prefers-reduced-motion: reduce)").matches || milliseconds <= 0) {
      this.setView(view);
      return;
    }
    const from = this.view();
    const to = {
      target: view.target ? view.target.clone() : from.target.clone(),
      distance: view.distance ?? from.distance,
      azimuth: view.azimuth ?? from.azimuth,
      polar: view.polar ?? from.polar,
    };
    // Take the short way round.
    let turn = (to.azimuth - from.azimuth) % TWO_PI;
    if (turn > Math.PI) turn -= TWO_PI;
    if (turn < -Math.PI) turn += TWO_PI;
    to.azimuth = from.azimuth + turn;
    this.flight = { from, to, elapsed: 0, duration: milliseconds };
    this.velocity.azimuth = this.velocity.polar = 0;
    this.onChange();
  }

  /** Advance animation by dt milliseconds. Returns true while something is still moving. */
  update(dt) {
    let moving = false;
    if (this.flight) {
      const flight = this.flight;
      flight.elapsed += dt;
      const t = ease(Math.max(0, Math.min(1, flight.elapsed / flight.duration)));
      this.target.lerpVectors(flight.from.target, flight.to.target, t);
      this.distance = Math.exp(Math.log(flight.from.distance) * (1 - t) + Math.log(flight.to.distance) * t);
      this.azimuth = flight.from.azimuth + (flight.to.azimuth - flight.from.azimuth) * t;
      this.polar = flight.from.polar + (flight.to.polar - flight.from.polar) * t;
      if (flight.elapsed >= flight.duration) this.flight = null;
      moving = true;
    } else if (Math.abs(this.velocity.azimuth) + Math.abs(this.velocity.polar) > 1e-5) {
      this.azimuth += this.velocity.azimuth;
      this.polar += this.velocity.polar;
      const damping = Math.pow(0.9, dt / 16.7);
      this.velocity.azimuth *= damping;
      this.velocity.polar *= damping;
      moving = true;
    }
    this.apply();
    return moving;
  }

  apply() {
    const { limits } = this;
    this.polar = Math.min(limits.maxPolar, Math.max(limits.minPolar, this.polar));
    this.distance = Math.min(limits.maxDistance, Math.max(limits.minDistance, this.distance));
    const sin = Math.sin(this.polar);
    this.camera.position.set(
      this.target.x + this.distance * sin * Math.sin(this.azimuth),
      this.target.y + this.distance * Math.cos(this.polar),
      this.target.z + this.distance * sin * Math.cos(this.azimuth)
    );
    this.camera.lookAt(this.target);
    const near = Math.max(0.01, this.distance / 150);
    const far = this.distance * 60 + 500;
    if (Math.abs(this.camera.near - near) > near * 0.05 || Math.abs(this.camera.far - far) > far * 0.05) {
      this.camera.near = near;
      this.camera.far = far;
      this.camera.updateProjectionMatrix();
    }
  }

  // ------------------------------------------------------------ input

  listen() {
    const element = this.element;
    element.style.touchAction = "none";
    this.handlers = {
      pointerdown: (event) => this.down(event),
      pointermove: (event) => this.move(event),
      pointerup: (event) => this.up(event),
      pointercancel: (event) => this.up(event),
      wheel: (event) => this.wheel(event),
      contextmenu: (event) => event.preventDefault(),
    };
    for (const [name, handler] of Object.entries(this.handlers)) {
      element.addEventListener(name, handler, { passive: false });
    }
  }

  dispose() {
    for (const [name, handler] of Object.entries(this.handlers)) this.element.removeEventListener(name, handler);
  }

  down(event) {
    if (!this.enabled) return;
    this.element.setPointerCapture?.(event.pointerId);
    this.pointers.set(event.pointerId, { x: event.clientX, y: event.clientY, button: event.button, shift: event.shiftKey });
    if (this.pointers.size === 1) {
      this.dragged = false;
      this.travel = 0;
    }
    this.flight = null;
    this.velocity.azimuth = this.velocity.polar = 0;
    this.pinch = this.pinchState();
  }

  move(event) {
    const pointer = this.pointers.get(event.pointerId);
    if (!pointer || !this.enabled) return;
    const dx = event.clientX - pointer.x;
    const dy = event.clientY - pointer.y;
    pointer.x = event.clientX;
    pointer.y = event.clientY;
    this.travel += Math.abs(dx) + Math.abs(dy);
    if (this.travel > 5) this.dragged = true;
    if (!this.dragged) return;
    if (this.pointers.size >= 2) {
      const now = this.pinchState();
      if (this.pinch && now) {
        this.distance *= this.pinch.spread / Math.max(1, now.spread);
        this.pan(now.x - this.pinch.x, now.y - this.pinch.y);
      }
      this.pinch = now;
    } else if (pointer.button === 2 || pointer.button === 1 || pointer.shift) {
      this.pan(dx, dy);
    } else {
      const speed = 0.0052;
      this.velocity.azimuth = -dx * speed;
      this.velocity.polar = -dy * speed;
      this.azimuth += this.velocity.azimuth;
      this.polar += this.velocity.polar;
    }
    this.apply();
    this.onChange();
  }

  up(event) {
    this.pointers.delete(event.pointerId);
    this.element.releasePointerCapture?.(event.pointerId);
    this.pinch = this.pinchState();
    this.onChange();
  }

  wheel(event) {
    if (!this.enabled) return;
    event.preventDefault();
    const step = event.deltaMode === 1 ? event.deltaY * 30 : event.deltaY;
    this.flight = null;
    this.distance *= Math.exp(Math.max(-240, Math.min(240, step)) * 0.0014);
    this.apply();
    this.onChange();
  }

  pinchState() {
    if (this.pointers.size < 2) return null;
    const [a, b] = [...this.pointers.values()];
    return { spread: Math.hypot(a.x - b.x, a.y - b.y), x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 };
  }

  pan(dx, dy) {
    // Move the target in the camera's plane, by the world size of one pixel at the target.
    const height = this.element.clientHeight || 1;
    const scale = (2 * this.distance * Math.tan((this.camera.fov * Math.PI) / 360)) / height;
    const right = new THREE.Vector3().setFromMatrixColumn(this.camera.matrix, 0);
    const up = new THREE.Vector3().setFromMatrixColumn(this.camera.matrix, 1);
    this.target.addScaledVector(right, -dx * scale).addScaledVector(up, dy * scale);
  }

  /** Keyboard steps, called by the viewer when the stage has focus. */
  nudge(key) {
    const step = 0.12;
    if (key === "ArrowLeft") this.azimuth -= step;
    else if (key === "ArrowRight") this.azimuth += step;
    else if (key === "ArrowUp") this.polar -= step;
    else if (key === "ArrowDown") this.polar += step;
    else if (key === "+" || key === "=") this.distance *= 0.85;
    else if (key === "-" || key === "_") this.distance /= 0.85;
    else return false;
    this.flight = null;
    this.apply();
    this.onChange();
    return true;
  }
}
