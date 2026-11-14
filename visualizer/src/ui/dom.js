// A tiny element builder. Text always goes in as text, never as markup.

export function h(tag, props = {}, ...children) {
  const element = document.createElement(tag);
  for (const [key, value] of Object.entries(props || {})) {
    if (value === null || value === undefined || value === false) continue;
    if (key === "class") element.className = value;
    else if (key === "dataset") Object.assign(element.dataset, value);
    else if (key.startsWith("on") && typeof value === "function") element.addEventListener(key.slice(2), value);
    else if (key in element && key !== "list") element[key] = value;
    else element.setAttribute(key, value === true ? "" : value);
  }
  for (const child of children.flat(Infinity)) {
    if (child === null || child === undefined || child === false) continue;
    element.append(child.nodeType ? child : document.createTextNode(String(child)));
  }
  return element;
}

export function emit(element, name, detail) {
  element.dispatchEvent(new CustomEvent(name, { detail, bubbles: true, composed: true }));
}

export function formatDate(iso) {
  if (!iso) return "";
  const [year, month, day] = iso.split("-").map(Number);
  const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  return `${day} ${months[month - 1]} ${year}`;
}

/** A small drawing of how a status looks in the scene: solid, outlined, dashed or crossed. */
export function statusSwatch(status) {
  const swatch = h("span", { class: `swatch swatch-${status || "unstated"}`, "aria-hidden": "true" });
  return swatch;
}
