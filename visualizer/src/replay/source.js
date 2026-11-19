// Getting one run into the page, as schema/RUN_VIEW.md fixes it ("Packaged for the
// viewer"): the run is inline in the page, or it is fetched from beside the page.

import { Run, validateReplay, validatePart, validateParts, PARTS_FORMAT } from "./run.js";

/** Base64 text to bytes, in a browser or in Node. */
export function decodeBase64(text) {
  if (typeof atob === "function") {
    const binary = atob(text);
    const bytes = new Uint8Array(binary.length);
    for (let index = 0; index < binary.length; index++) bytes[index] = binary.charCodeAt(index);
    return bytes.buffer;
  }
  const buffer = Buffer.from(text, "base64");
  return buffer.buffer.slice(buffer.byteOffset, buffer.byteOffset + buffer.byteLength);
}

/** A run file (parsed JSON) as a Run. Throws with the first problems found if it breaks the contract. */
export function openReplay(file, entry = null) {
  const problems = validateReplay(file);
  if (problems.length) throw new Error(`the run file does not follow the replay format: ${problems.slice(0, 3).join("; ")}`);
  const buffer = decodeBase64(file.payload.data);
  if (buffer.byteLength !== file.payload.byte_length) {
    throw new Error(`the run's arrays are ${buffer.byteLength} bytes long, not the ${file.payload.byte_length} stated`);
  }
  return new Run(file.view, buffer, entry);
}

/**
 * Load the run a catalogue entry names. It is looked for in the page first
 * (<script type="application/json" data-replay="id">), then fetched from `entry.file`,
 * a URL relative to the page.
 */
export async function loadRun(entry, { root = globalThis.document, fetcher = globalThis.fetch } = {}) {
  let file = null;
  const inline = root?.querySelector?.(`script[type="application/json"][data-replay="${entry.id}"]`);
  if (inline) {
    file = JSON.parse(inline.textContent);
  } else {
    if (!entry.file) throw new Error("the catalogue gives no file for this run");
    if (typeof fetcher !== "function") throw new Error("this page cannot fetch the run");
    const response = await fetcher(entry.file);
    if (!response.ok) throw new Error(`${entry.file} answered ${response.status}`);
    file = await response.json();
  }
  const run = openReplay(file, entry);
  if (run.id !== entry.id) throw new Error(`the file holds run ${run.id}, not ${entry.id}`);
  return run;
}

// The files of a run's parts that are fetched or on their way, for the parts not yet taken in: run -> file -> a promise
// of { part id: its arrays }. A file of several parts is fetched once, however many of its parts are asked for; a part is
// taken out when it is taken in, and a file that could not be fetched is forgotten, so that it is asked for again.
const fetched = new WeakMap();

/**
 * Fetch one part of a run: records that come in a file of their own beside the run's, so
 * that the run's own file stays small (schema/QUANTITY_LAYERS.md, rule 10). It is looked
 * for in the page first (<script type="application/json" data-replay-part="run-id/part">),
 * then fetched. The file is the one the catalogue's line for the run names for the part
 * (`entry.parts`), else the one the run's view names: a file of that part alone
 * (cells.visualizer.replay_part@1), or one of several of the run's parts
 * (cells.visualizer.replay_parts@1), as the published page packages them (schema/RUN_VIEW.md,
 * "Parts published together"). Only the part asked for is taken in. Resolves when its
 * records can be read; an error names the file and the part.
 */
export async function loadPart(run, partId, { root = globalThis.document, fetcher = globalThis.fetch } = {}) {
  const part = run.parts.get(partId);
  if (!part) throw new Error(`the run has no part ${partId}`);
  if (part.loaded) return run;
  if (part.loading) return part.loading;
  const name = run.entry?.parts?.find?.((item) => item?.id === partId)?.file || part.file;
  part.loading = (async () => {
    const inline = root?.querySelector?.(`script[type="application/json"][data-replay-part="${run.id}/${partId}"]`);
    const where = inline ? `the page's copy of ${run.id}/${partId}` : `${name} (the part ${partId})`;
    try {
      if (inline) {
        const file = JSON.parse(inline.textContent);
        const problems = validatePart(file, run.id, partId);
        if (problems.length) throw new Error(problems[0]);
        run.attach(partId, decodeBase64(file.payload.data));
      } else {
        const { arrays, done } = await fetchedPart(run, partId, name, fetcher);
        run.attach(partId, arrays);
        done();
      }
    } catch (error) {
      if (!inline) fetched.get(run)?.delete(name); // a file whose part could not be taken in is fetched again when asked for again
      throw new Error(`${where}${/^answered /.test(error.message) ? " " : ": "}${error.message}`);
    }
    return run;
  })();
  try {
    return await part.loading;
  } finally {
    part.loading = null;
  }
}

/**
 * The arrays of one part from the file `name`, fetched once for the run whatever else of it is asked for, and `done`, which
 * lets them go once the run has taken them in (and the file, once all its parts are in).
 */
async function fetchedPart(run, partId, name, fetcher) {
  if (!fetched.has(run)) fetched.set(run, new Map());
  const files = fetched.get(run);
  if (!files.has(name)) {
    if (typeof fetcher !== "function") throw new Error("this page cannot fetch the run's records");
    const promise = (async () => {
      const response = await fetcher(name);
      if (!response.ok) throw new Error(`answered ${response.status}`);
      const file = await response.json();
      const several = file?.format === PARTS_FORMAT;
      const problems = several ? validateParts(file, run.id) : validatePart(file, run.id, partId);
      if (problems.length) throw new Error(problems[0]);
      return new Map((several ? file.parts : [file]).map((item) => [item.part, decodeBase64(item.payload.data)]));
    })();
    files.set(name, promise);
    promise.catch(() => files.get(name) === promise && files.delete(name));
  }
  const promise = files.get(name), held = await promise;
  if (!held.has(partId)) throw new Error(`the file holds no part ${partId}`);
  const done = () => {
    held.delete(partId);
    if (!held.size && files.get(name) === promise) files.delete(name);
  };
  return { arrays: held.get(partId), done };
}
