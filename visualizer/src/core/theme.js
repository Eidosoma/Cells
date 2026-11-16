// Colours come from CSS custom properties on the page's :root, so the 3D scene and
// the interface follow the viewer's theme together. Nothing here holds a colour.

const TOKENS = [
  "bg", "bg-raised", "fg", "muted", "line", "accent",
  "plate", "plate-edge", "edge", "ghost",
  "st-qualified", "st-landed", "st-established", "st-designed", "st-planned",
  "st-failed", "st-external", "st-unstated",
  "kind-requires", "kind-writes", "kind-conflicts", "kind-runs", "kind-extends",
  "bio-membrane", "bio-cyto", "bio-nucleus", "bio-er", "bio-ribosome", "bio-mito", "bio-protein", "bio-pump",
  "bio-fuel", "bio-water", "bio-signal", "bio-ion", "bio-wound", "bio-cell", "bio-chloroplast",
  "atlas-generic",
  "seq-0", "seq-1", "seq-2", "seq-3", "seq-4",
];

const camel = (name) => name.replace(/-([a-z0-9])/g, (_, letter) => letter.toUpperCase());

export function readPalette(element) {
  const style = getComputedStyle(element);
  const palette = {};
  for (const token of TOKENS) palette[camel(token)] = style.getPropertyValue(`--${token}`).trim() || "#888888";
  palette.dark = style.getPropertyValue("--is-dark").trim() === "1";
  return palette;
}

/** Calls back whenever the page's theme may have changed (system setting or the host's toggle). */
export function watchTheme(callback) {
  const media = matchMedia("(prefers-color-scheme: dark)");
  media.addEventListener("change", callback);
  const observer = new MutationObserver(callback);
  observer.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme", "class", "style"] });
  return () => {
    media.removeEventListener("change", callback);
    observer.disconnect();
  };
}

export const statusToken = (status) => camel(`st-${status || "unstated"}`);
