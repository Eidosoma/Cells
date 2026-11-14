// Text labels drawn as HTML over the canvas, so they stay sharp, follow the theme
// and can be clicked. Each label follows a point in the scene. Two ways to place them:
//   in place   just above its point; where labels would overlap, the more important wins;
//   callout    in a column beside the subject, joined to its point by a leader line,
//              the way a textbook figure is labelled. Used when a lens gives a frame.

import * as THREE from "../three.js";

const SVG = "http://www.w3.org/2000/svg";
const COLUMN_GAP = 30; // from the subject's edge to the label column
const ROW_GAP = 5;

export class LabelLayer {
  constructor(container, stage) {
    this.container = container;
    this.stage = stage;
    this.labels = [];
    this.keepClear = { top: 56 }; // the top bar: labels stay out from under it
    this.calloutFrame = null; // () => { x, y, radius } in pixels, or null
    this.blocked = null; // () => [{ left, top, right, bottom }] of panels labels must avoid
    this.scratch = new THREE.Vector3();
    this.leaders = document.createElementNS(SVG, "svg");
    this.leaders.setAttribute("class", "leaders");
    this.container.append(this.leaders);
  }

  /**
   * spec: { id, text, anchor: Vector3, priority, kind, lift, swatch, callout }.
   * priority: higher wins a collision. kind becomes a CSS class. lift: pixels above the anchor.
   * swatch: a status id, drawn as a dot before the text. callout: may be placed in a column.
   */
  add(spec) {
    const element = document.createElement(spec.id ? "button" : "div");
    element.className = `label label-${spec.kind || "part"}`;
    if (spec.swatch) {
      const dot = document.createElement("span");
      dot.className = `swatch swatch-${spec.swatch}`;
      dot.setAttribute("aria-hidden", "true");
      element.append(dot);
    }
    element.append(spec.text);
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
    if (spec.callout) {
      label.path = document.createElementNS(SVG, "path");
      label.dot = document.createElementNS(SVG, "circle");
      label.dot.setAttribute("r", "2.6");
      this.leaders.append(label.path, label.dot);
      this.lead(label, false);
    }
    element.classList.add("is-off");
    this.labels.push(label);
    return label;
  }

  clear() {
    for (const label of this.labels) {
      label.element.remove();
      label.path?.remove();
      label.dot?.remove();
    }
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
    const frame = this.calloutFrame ? this.calloutFrame() : null;
    const inPlace = [], callouts = [];
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
      (frame && label.callout ? callouts : inPlace).push(label);
    }
    const placed = [];
    const left = this.column(callouts.filter((label) => this.sideOf(label, frame) === "left"), "left", frame, placed);
    const right = this.column(callouts.filter((label) => label.side === "right"), "right", frame, placed);
    this.placeInPlace([...inPlace, ...left, ...right], placed);
  }

  /** Which side of the subject a label's point is on, with a little stickiness so it does not flicker. */
  sideOf(label, frame) {
    const side = label.x < frame.x ? "left" : "right";
    if (!label.side || Math.abs(label.x - frame.x) > 16) label.side = side;
    return label.side;
  }

  /**
   * Places one column of callout labels. Returns the labels it could not take
   * (no room on that side), which are then placed in place.
   */
  column(labels, side, frame, placed) {
    if (!labels.length) return [];
    const { width, height } = this.stage;
    const edge = side === "left" ? frame.x - frame.radius - COLUMN_GAP : frame.x + frame.radius + COLUMN_GAP;
    const widest = Math.max(...labels.map((label) => label.width));
    const span = side === "left" ? [edge - widest, edge] : [edge, edge + widest];
    if (span[0] < 6 || span[1] > width - 6) return labels;
    // The column may use the tallest stretch that no panel covers.
    const covered = (this.blocked ? this.blocked() : [])
      .filter((rect) => rect.right > span[0] && rect.left < span[1])
      .map((rect) => [rect.top - 8, rect.bottom + 8])
      .sort((a, b) => a[0] - b[0]);
    let top = this.keepClear.top + 8, bottom = top, cursor = top;
    for (const [from, to] of [...covered, [height - 70, height]]) {
      if (from - cursor > bottom - top) [top, bottom] = [cursor, from];
      cursor = Math.max(cursor, to);
    }
    if (bottom - top < 60) return labels;
    labels.sort((a, b) => a.y - b.y);
    const tops = labels.map((label) => label.y - label.height / 2);
    for (let index = 0; index < tops.length; index++) {
      tops[index] = Math.max(tops[index], index ? tops[index - 1] + labels[index - 1].height + ROW_GAP : top);
    }
    for (let index = tops.length - 1; index >= 0; index--) {
      const limit = index === tops.length - 1 ? bottom - labels[index].height : tops[index + 1] - labels[index].height - ROW_GAP;
      tops[index] = Math.min(tops[index], limit);
    }
    const spill = [];
    labels.forEach((label, index) => {
      if (tops[index] < top - 0.5) {
        spill.push(label); // the column is full
        return;
      }
      const x = Math.round(side === "left" ? edge - label.width : edge);
      const y = Math.round(tops[index]);
      label.element.style.transform = `translate(${x}px, ${y}px)`;
      label.element.classList.add("is-callout");
      this.show(label, true);
      placed.push({ left: x - 3, top: y - 2, right: x + label.width + 3, bottom: y + label.height + 2 });
      const mid = y + label.height / 2;
      const start = side === "left" ? edge + 4 : edge - 4;
      const elbow = side === "left" ? edge + 16 : edge - 16;
      label.path.setAttribute("d", `M${start} ${mid} L${elbow} ${mid} L${label.x.toFixed(1)} ${label.y.toFixed(1)}`);
      label.dot.setAttribute("cx", label.x.toFixed(1));
      label.dot.setAttribute("cy", label.y.toFixed(1));
      this.lead(label, true);
    });
    return spill;
  }

  placeInPlace(labels, placed) {
    // Important labels first; among equals, the nearer one.
    labels.sort((a, b) => b.priority + b.boost - (a.priority + a.boost) || a.depth - b.depth);
    for (const label of labels) {
      if (label.callout) {
        label.element.classList.remove("is-callout");
        this.lead(label, false);
      }
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

  /** Show or hide a label's leader line, matching the label's own emphasis. */
  lead(label, on) {
    if (!label.path) return;
    const state = !on ? "off" : label.element.classList.contains("is-focus") ? "focus" : label.element.classList.contains("is-dim") ? "dim" : "on";
    if (label.leadState === state) return;
    label.leadState = state;
    label.path.setAttribute("class", `lead-${state}`);
    label.dot.setAttribute("class", `lead-${state}`);
  }

  show(label, on) {
    if (!on && label.path) this.lead(label, false);
    if (label.shown === on) return;
    label.shown = on;
    label.element.classList.toggle("is-off", !on);
  }
}
