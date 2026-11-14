// Text labels drawn as HTML over the canvas, so they stay sharp, follow the theme
// and can be clicked. Each label follows a point in the scene; where labels would
// overlap, the more important one wins.

import * as THREE from "../three.js";

export class LabelLayer {
  constructor(container, stage, onPick) {
    this.container = container;
    this.stage = stage;
    this.onPick = onPick;
    this.labels = [];
    this.keepClear = { top: 56 }; // the top bar: labels stay out from under it
    this.scratch = new THREE.Vector3();
    this.container.addEventListener("click", (event) => {
      const button = event.target.closest("[data-label]");
      if (button) this.onPick(button.dataset.label);
    });
  }

  /**
   * spec: { id, text, anchor: Vector3, priority, kind, lift }.
   * priority: higher wins a collision. kind becomes a CSS class. lift: pixels above the anchor.
   */
  add(spec) {
    const element = document.createElement(spec.id ? "button" : "div");
    element.className = `label label-${spec.kind || "part"}`;
    element.textContent = spec.text;
    if (spec.id) {
      element.dataset.label = spec.id;
      element.type = "button";
      element.tabIndex = -1;
    }
    this.container.append(element);
    const label = {
      ...spec,
      element,
      priority: spec.priority ?? 0,
      lift: spec.lift ?? 10,
      width: element.offsetWidth,
      height: element.offsetHeight,
      shown: false,
      hidden: false,
      boost: 0,
    };
    element.classList.add("is-off");
    this.labels.push(label);
    return label;
  }

  clear() {
    for (const label of this.labels) label.element.remove();
    this.labels = [];
  }

  /** Re-measure after fonts load or text changes. */
  measure() {
    for (const label of this.labels) {
      label.width = label.element.offsetWidth;
      label.height = label.element.offsetHeight;
    }
  }

  /** Place every label for the current camera. Call after each rendered frame. */
  layout() {
    const { stage, scratch } = this;
    const { width, height } = stage;
    const candidates = [];
    for (const label of this.labels) {
      if (label.hidden) {
        this.show(label, false);
        continue;
      }
      stage.project(label.anchor, scratch);
      if (scratch.z > 1 || scratch.z < -1 || scratch.x < -40 || scratch.x > width + 40 || scratch.y < -20 || scratch.y > height + 40) {
        this.show(label, false);
        continue;
      }
      label.x = scratch.x;
      label.y = scratch.y;
      label.depth = scratch.z;
      candidates.push(label);
    }
    // Important labels first; among equals, the nearer one.
    candidates.sort((a, b) => b.priority + b.boost - (a.priority + a.boost) || a.depth - b.depth);
    const placed = [];
    for (const label of candidates) {
      const left = Math.round(label.x - label.width / 2);
      const top = Math.round(label.y - label.height - label.lift);
      if (top < this.keepClear.top) {
        this.show(label, false);
        continue;
      }
      const box = { left: left - 3, top: top - 2, right: left + label.width + 3, bottom: top + label.height + 2 };
      const forced = label.boost >= 1000;
      const clash = !forced && placed.some((other) => box.left < other.right && box.right > other.left && box.top < other.bottom && box.bottom > other.top);
      if (clash) {
        this.show(label, false);
        continue;
      }
      placed.push(box);
      label.element.style.transform = `translate(${left}px, ${top}px)`;
      this.show(label, true);
    }
  }

  show(label, on) {
    if (label.shown === on) return;
    label.shown = on;
    label.element.classList.toggle("is-off", !on);
  }
}
