// Builds the one page that every delivery mode uses: the local server, the
// standalone file and the artifact all get this same HTML.

import { build } from "esbuild";
import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import path from "node:path";

export const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
export const THREE_VERSION = "0.170.0";
// Published pages may load scripts only from a short list of CDNs; cdnjs is the preferred one.
export const THREE_CDN = `https://cdnjs.cloudflare.com/ajax/libs/three.js/${THREE_VERSION}/three.module.min.js`;
export const THREE_LOCAL = "/vendor/three.module.min.js";
export const DEFAULT_SCENE = path.join(ROOT, "data", "architecture", "architecture.scene.json");

// The document the artifact service wraps around a published page (read back from a
// published artifact on 14 November 2026). Local previews use the same wrapper.
const SKELETON_HEAD =
  '<meta charset=utf8><meta name=viewport content="width=device-width,initial-scale=1,viewport-fit=cover">' +
  "<style>:root{color-scheme:light;box-sizing:border-box;padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}" +
  "html{scroll-padding-top:env(safe-area-inset-top,0px)}body{margin:0;padding:0;font:14px -apple-system,BlinkMacSystemFont,sans-serif;background:#fff;color:#000}" +
  "img{max-width:100%}[hidden]:not([hidden=until-found i]){display:none!important}</style>";

/** The page content, as published: no doctype, html, head or body tags of its own. */
export async function buildPage({ scenePath = DEFAULT_SCENE, three = THREE_CDN } = {}) {
  const bundle = await build({
    entryPoints: [path.join(ROOT, "src", "main.js")],
    bundle: true,
    format: "esm",
    target: "es2022",
    write: false,
    minify: false,
    legalComments: "none",
    plugins: [
      {
        name: "three-from-url",
        setup(api) {
          api.onResolve({ filter: /^three$/ }, () => ({ path: three, external: true }));
        },
      },
    ],
  });
  const script = bundle.outputFiles[0].text.replaceAll("</script", "<\\/script");
  const scene = JSON.stringify(JSON.parse(await readFile(scenePath, "utf8"))).replaceAll("<", "\\u003c");
  const css = await readFile(path.join(ROOT, "src", "page.css"), "utf8");
  const template = await readFile(path.join(ROOT, "src", "page.html"), "utf8");
  return template
    .replace("/*__PAGE_CSS__*/", () => css.trim())
    .replace("__SCENE__", () => scene)
    .replace("/*__BUNDLE__*/", () => script.trim());
}

/** The page as a complete document, for a file on disk or the local server. */
export function wrap(content, { theme = null, head = "" } = {}) {
  const attribute = theme ? ` data-theme="${theme}"` : "";
  return `<!doctype html><html${attribute}><head>${SKELETON_HEAD}${head}</head><body>\n${content}\n</body></html>\n`;
}

/** A Content-Security-Policy close to the artifact frame's, so a blocked load shows up locally. */
export function contentSecurityPolicy({ local = false } = {}) {
  const scripts = ["'unsafe-inline'", "https://cdnjs.cloudflare.com", "https://cdn.jsdelivr.net/npm/", "https://unpkg.com", "https://cdn.tailwindcss.com", "https://code.jquery.com"];
  if (local) scripts.push("'self'");
  return [
    "default-src 'none'",
    `script-src ${scripts.join(" ")}`,
    "style-src 'unsafe-inline' https://fonts.googleapis.com",
    "font-src https://fonts.gstatic.com data:",
    "img-src 'self' data: blob:",
    "connect-src 'self'",
    "worker-src 'self' blob:",
  ].join("; ");
}
