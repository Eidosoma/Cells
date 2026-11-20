# Hosting the viewer at cells.eidosoma.ai, and an API for its data

Status: **a review for the owner, 19 November 2026, with the owner's answers of the same day.**
Sections 1 to 8 are the review as it was written: they recommend kinds of service and the
properties that matter; where a product is named, it is an example, not a choice, and nothing
about it was checked. **Section 9 records what the owner then decided, and what each decision
changes in the sections before it; where the two differ, section 9 stands.** Nothing is set up,
bought or deployed yet. It is tooling: the viewer runs no engine model, so by the project's rules
this work needs the owner's explicit approval as tooling.

The numbers are measured on the staged folder of **Version 47**, the last published page (8
species), unless they are marked otherwise. The branch's head (f6e8e391) adds the frog, the ninth
species; its figures are read from `tools/references/fetches.json` and `docs/XENOPUS.md`, not
measured, because no staged folder holds it yet. Compression was measured on every file of the
staged folder (Node's own zlib: gzip at levels 6 and 9, brotli at qualities 5 and 11). **Gzip**
and **brotli** are the two ways browsers accept files compressed: the server sends the smaller
form and the browser unpacks it, with no change to the file itself.

**Measured since, on the staged folder of Version 48** (published 19 November 2026, with the
frog; gzip level 6, brotli quality 11): 467 files, 168.3 MB raw, 58.2 MB with gzip (34.6%), 45.0 MB
with brotli (26.7%). The page is 5,059,860 bytes raw, 879,407 with gzip and 593,925 with brotli.
The frog's eight files are 12.1 MB raw, 1.7 MB with gzip and 1.2 MB with brotli. The headline
numbers below were also measured a second time, by another script, and agree.

## In short

- **Decided since (section 9):** the site is served from a machine of the project's own, in a
  container the owner sets up, not from a rented store; releases are marked by tags in the
  repository; the site serves three.js and the fonts itself; and the API's only user, for now,
  is the viewer. The three points below are the review's own, as it was written.
- **Host** the staged folder as a static site: files in object storage behind a content delivery
  network, each release in a folder of its own that never changes, and a small root page that
  names the current release. A release is one command from the staged folder; a rollback is
  rewriting that root page.
- **Build** once. The artifact and the site are published from the same staged folder, byte for
  byte; the site adds only a document wrapper, a base address and a short host profile, each
  written by a tool and held by a test.
- **The API starts as files.** Document the files the site already serves (each already carries a
  versioned `format`), add an index of what exists, JSON Schemas for the formats, open
  cross-origin reads and a written promise of what will not change. Add a read-only service only
  when the queries outgrow files built ahead of time. Leave runs on request to the engine's owner.

Three measured numbers drive most of the choices:

| | Raw | gzip (level 6) | brotli (quality 11) |
| --- | ---: | ---: | ---: |
| One release: the page and 458 files beside it | 155.5 MB | 56.5 MB (36.3%) | 43.8 MB (28.2%) |
| A first visit to the opening view (page, three.js, the planarian's loop; fonts not counted) | 5.15 MB | 1.02 MB | 0.75 MB |
| The run files, three quarters of the bytes (341 files) | 114.5 MB | 49.1 MB (42.9%) | 38.3 MB (33.5%) |

A first visit costs about a fifth of its raw size when the host compresses; of the 1.02 MB, the
site itself would send 0.85 MB (0.61 MB with brotli), and three.js comes from cdnjs. The runs
compress worst because their numbers are binary arrays written as **base64** (binary bytes spelt
out in 64 letters and signs, a third larger) inside JSON. And the project
publishes often: `artifacts.json` records 69 versions from 14 to 19 November 2026, between 5 and
23 a day, and in four of the last five publishes only 4.3 to 8.9 MB of the 155 MB changed.

---

## 1. What is being hosted

**In brief.** The site would serve exactly what the artifact serves: one page of 4.3 MB that
carries the viewer's code and its scene, and 458 data files beside it, 155.5 MB in all. Compression
would cut what a visitor downloads about five-fold on a first visit. The artifact host's limits
shaped how the files are cut, but nothing in them stops the same files working on a site of their
own.

### The files, by kind (Version 47, measured)

| Kind | Files | Raw bytes | gzip 6 | brotli 11 | Fetched |
| --- | ---: | ---: | ---: | ---: | --- |
| The page (`cells-architecture.html`) | 1 | 4,341,505 | 813,995 (18.7%) | 582,170 (13.4%) | every visit |
| Runs and their parts (`runs/`) | 341 | 114,486,668 | 42.9% | 33.5% | when a run or a layer is shown |
| Species' own proteins (`proteins/<species>/`) | 70 | 31,144,309 | 15.7% | 11.6% | when a species' proteins are shown or searched |
| Machine shapes (`shapes/`) | 21 | 3,085,131 | 34.8% | 25.5% | at a machine's Shape level |
| Machine benches (`catalogue/`) | 8 | 1,632,066 | 12.0% | 8.8% | when a species' bench is shown |
| The assembly's runs (`models/gard/`) | 2 | 275,894 | 37.0% | 31.4% | the assembly's view |
| Stills of the landing's cards (`stills/`, JPEG) | 14 | 277,203 | 96.3% | 95.1% | near the screen on the landing |
| The landing's cards (`cards.json`) | 1 | 164,078 | 14.3% | 11.5% | the Experiments landing |
| A machine's closer view (`machines/`) | 1 | 64,963 | 22.6% | 19.1% | "Look closer" |
| **All** | **459** | **155,471,817** | **56,494,242** | **43,809,266** | |

Gzip at level 9 gains almost nothing over level 6 (36.2% against 36.3%). Brotli at quality 11 is
about a fifth smaller than gzip; quality 5, the kind of setting a server uses when it compresses as
it sends, sits between them (33.4%). The pictures are JPEG already and do not compress.

The median file is 256 KB and nine in ten are under 775 KB. The largest are the page (4.3 MB;
5.06 MB at head) and the species' search files (`names.json`, up to 1.8 MB; the frog's is 2.7 MB at
head). With the frog, a release would hold 467 files: its shelves, six members' files and its names
file, about 12 MB more, by `docs/XENOPUS.md`.

**What is inside the page.** The page is self-contained apart from three.js and two web fonts:

| Part | Raw | gzip 6 | brotli 11 |
| --- | ---: | ---: | ---: |
| The scene, a JSON block (its largest part, `entities`, is 1.6 MB) | 2,406,573 | 297,714 | 184,228 |
| The viewer's code, one module script, not minified | 1,928,664 | 513,966 | 397,895 |
| The page's style | 5,482 | | |

Minifying the code (esbuild's own option, measured on the head's code) takes it from 1.86 MB to
1.12 MB, and from 501 KB to 371 KB gzipped: about 130 KB less on every first visit, on either
host. That is independent of where the page is hosted.

**Loaded from elsewhere on every visit:** three.js 0.170.0 from cdnjs (691,648 bytes; 172,158
gzipped, 139,117 brotli, measured on the same file in `node_modules`), and the Inter and Space
Grotesk fonts from Google Fonts (a style sheet and its font files, not measured). These are the
only requests to other parties; they matter for privacy (section 6).

### What a first visit to each tab fetches

The page is fetched at every address. Beside it:

| Address | Fetched beside the page | Raw | gzip / brotli | Basis |
| --- | --- | ---: | ---: | --- |
| Scope, the site's first entry | the planarian's looping run and the parts its flux draws, about 5 files | about 120 KB (bound 133,000) | about 33 KB / 27 KB | the fetch budget, and the five files the flux draws, from the code |
| Experiments landing (`lens=experiments`) | `cards.json` and the first band's two stills | 263,102 (3 files; bound 289,000) | 101,738 / 96,459 | measured by the gate, 20 November 2026, with its thirtieth card; the cards are 189,140 of it raw, and 27,776 / 22,497 compressed |
| The tumour tissue's card (`part=gap-junction-tissue-sheet`) | the sheet's and the line's runs and parts | 2,817,063 (10 files) | not measured | measured by the gate |
| The assembly (`example=gard`) | its two files | 275,894 | 102,181 / 86,765 | the fetch budget, and file sizes |
| A single run of the networks | its own file | under 40,000 | | the fetch budget |
| Machines, planarian | the planarian's bench | 313,297 | 23,697 / 17,575 | from the code (`machines_card.js`) and file sizes, not measured in a browser |
| Proteins, planarian | its shelves as the tab opens, whichever of its two modes is drawn (`setMode` in `proteins.js`); a family's members' file (up to 1.1 MB) when one opens; the names file (1,127,815) when the search is used | 640,492 | 121,890 / 87,567 | from the code and file sizes, not measured in a browser |
| Engine, Laws | nothing | 0 | | from the code, not measured |

A first visit to Scope therefore moves 5.15 MB raw (the page, three.js, the run), 1.02 MB with
gzip and 0.75 MB with brotli, not counting the fonts, in about ten requests (the page, three.js,
the font style sheet and its font files, about five run files). The page never fetches every experiment at once:
`tools/check_fetches.mjs` holds each address to `tools/references/fetches.json`.

### What the artifact host forces today, and what a site of our own would not

| The artifact host | What it led to | On a site of our own |
| --- | --- | --- |
| At most 511 files and 256 MB in a version, and 255 files and 64 MB in one publish | A full set goes up in several uploads (`tools/stage_publish.py` orders removals first and counts every upload). The parts of a run are packed into one or two files (`parts_together`, 341 files for 112 runs). Members of the largest catalogues are cut 2,000 to a file, the frog's 6,000, "since the page holds at most 511" (`docs/XENOPUS.md`) | No practical limit on files. The packing can stay as it is (section 3) |
| No query strings: only the outer link's `#name` reaches the page | A view can be linked by its tab's name and nothing finer: a card's detail, a run, a species or a selected part has no shareable link | `?lens=…&select=…&entry=…` work as they do on the local server: the viewer already reads them and writes them back |
| Unknown compression | The page could not be measured as delivered; budgets are in raw bytes | Compression is set, and checked in the read-back |
| Scripts only from a short list of CDNs; fonts from Google Fonts | three.js from cdnjs; the fonts from Google | three.js and the fonts could be served by the site itself |
| The host wraps the page in a document of its own (a short head read back each time) | `tools/lib/build_page.mjs` copies that wrapper for local previews (`wrap`) | The same wrapper, written by the release tool |
| A link can be updated only from the account that published it | The page has stood at more than one link; `artifacts.json` records them | One address, kept |
| Its own response headers and content policy | The page is checked locally under an approximation of the frame's policy; the real frame's policy is checked only by eye | The site sets its own headers (section 6) |
| Private by default, shared from its own menu | | Public by default, unless the owner wants it otherwise |

One measurement is worth keeping for later. In a sample of 35 of the 341 run files, 94.6% of the
bytes are the base64 text of the arrays. Served as raw binary beside the same files' other text,
the sample would compress to 4.6 MB with gzip and 3.0 MB with brotli, where the JSON files
compress to 5.2 MB and 4.0 MB: 11% to 25% less on the wire. That would need a new packaged format,
so it is an option, not a step.

---

## 2. Hosting cells.eidosoma.ai

**Recommendation.** Serve the staged folder as a static site: the files in object storage behind a
content delivery network, each release under a folder of its own that never changes
(`/r/v48/`), and a root page that names the current release. A release is one command run on the
machine that made the staged folder; rolling back is rewriting the root page, in seconds. Pick a
provider whose network compresses JSON files of up to about 5 MB as it sends them, or that serves
compressed copies the release uploads beside the files.

Terms used here. **Object storage** keeps files ("objects") under names, behind an interface for
uploading and listing them. A **content delivery network (CDN)** is a set of servers near visitors
that keeps copies of the files and answers for them. The server the CDN fetches from is the
**origin**. **Egress** is the bytes sent out to visitors, which most providers charge for. A file
that **never changes** can be cached by browsers and the CDN for a year, so a repeat visit costs
almost nothing.

### One fact shapes every option

**A release cannot be built from the repository alone.** The run files are remade from the
engine's frozen evidence, which is not in git (`out/runs/` is ignored; README, "From a fresh
checkout"); the scene is extracted from a checkout of the engine at a reviewed revision; and the
members' and names files are written by the page builder. So "deploy from the repository" means,
for every option, **build and stage on the machine that has the evidence, then upload the staged
folder.** A platform that builds the site from git on its own servers cannot make this site. This
also decides who can deploy (section 6).

### The options

**A. Object storage behind a CDN.** The release tool uploads the staged folder under `/r/<id>/`
and then rewrites the root page. Examples of the kind: a cloud provider's storage with its CDN in
front, or a CDN company's own storage.

**B. A static-site platform, fed a prebuilt folder.** The platform's command-line tool uploads the
folder as a "deploy"; the platform keeps every deploy, can put any earlier one back, gives each
one a preview address, compresses and sets headers from a file in the folder. Examples of the
kind: Netlify, Cloudflare Pages, Vercel, GitHub Pages. What is said of the kind here (keeping
every deploy, preview addresses, which headers a site may set) is typical of the kind and is to be
verified for any one platform; none was looked up for this review.

**C. A small server of our own**, a virtual machine or a container running a web server (Caddy and
nginx are examples) with a CDN in front, serving the folder and choosing between precompressed
copies itself.

| Criterion | A. Storage and CDN | B. Static-site platform | C. Own server |
| --- | --- | --- | --- |
| Release in one step from the staged folder | Yes: one script (upload, check, move the pointer) | Yes: the platform's upload command | Yes: copy the folder and switch a link on the server |
| Versioned releases that never change, at our own address | Yes: `/r/<id>/` folders stay | Typically each deploy is kept at the platform's own preview address, not under our domain (to verify). Keeping older releases under `/r/` would then mean uploading them again in every deploy, which multiplies files | Yes |
| A "latest" pointer and instant rollback | Rewrite the root page (seconds, plus clearing it from the CDN's cache) | Built in: put an earlier deploy back | Switch a link |
| Compression | Depends on the CDN: check which types and sizes it compresses as it sends (our files reach 5.1 MB), or upload compressed copies with the right headers | Usually automatic; check the size limit | Full control: compress once at release, serve the copies |
| Headers (cache, content policy, cross-origin) | Per file at upload, or by CDN rules | From a headers file in the folder | Full control |
| Real addresses (query strings, later paths) | Query strings: yes. Paths: a rewrite rule at the CDN | Query strings: yes. Paths: a rewrite rule in the platform's file | Yes |
| File-count limit | None in practice | Per deploy: look up the platform's limits against 467 files, a largest file of 5.1 MB and 168 MB a deploy | None |
| Cost drivers | Storage per GB-month, egress per GB, requests | Often a plan with a bandwidth allowance: look up the allowance and what happens past it | The machine's rent, plus CDN egress |
| Operations burden | Low to medium: storage policy, CDN rules, certificate, one script | Lowest: the platform does certificates, caching and rollback | Highest: updates, certificates, uptime, attacks, backups |
| Staging against production | A new release is reachable at `/r/<id>/` before the pointer moves | Preview deploys | A second folder or name |

**Why A.** It is the only option that gives, at once, releases under our own address that never
change, no file limits, full control of headers, and almost no software to keep up. Releases that
never change matter here for the same reason `artifacts.json` exists: a link to a release shows
what was published that day, and the record can say which release a statement was made on. B is
the simpler choice if the owner does not need old releases under our own domain; C only earns its
burden once there is a service to run anyway (Stage 1 or 2), and even then the files are better
served from storage and the server kept for the service.

**What would change this recommendation.** If the chosen provider's CDN will not compress files of
this size and cannot serve uploaded compressed copies, choose another provider, or C. If a
platform of kind B turns out to keep older deploys reachable under our own domain, or the owner
wants no cloud account to manage and accepts older releases at the platform's own addresses, B. If
traffic turns out large enough that egress prices dominate, compare a flat-rate plan.

### The layout

```
/index.html                       the pointer: a copy of the current release's root.html
/r/v48/index.html                 the release's page, wrapped as the artifact host wraps it
/r/v48/root.html                  the same page with <base href="/r/v48/">, to be copied to /index.html
/r/v48/runs/…  proteins/…  …       the files, at the same paths as beside the artifact
/r/v48/release.json               what the release is (section 4)
/r/v47/…                          the release before, unchanged
/formats/<format>/<major>.schema.json   the formats, once Stage 0 exists
```

Every file the page fetches is addressed relative to the page (`loadBeside` in
`src/lenses/protein_shelves.js`, `loadRun` and `loadPart` in `src/replay/source.js`, the cards and
stills in `src/ui/landing.js`). So the page at `/r/v48/` works with no change, and the root page
works with one line more, a `<base href="/r/v48/">`, which sends its fetches to the release it
came from. That matters: a visitor who opened the page an hour before a release keeps fetching
the files of their own release, which still exist, and never a mix of two. A base address also
changes how the page's own relative addresses resolve. A search of the viewer's code found one
place that must change (section 3) and no other: no link to an anchor, no link made of a query
alone, and no SVG reference to a fragment (`url(#…)`, `<use>`), which browsers have not always
resolved alike under a base address. A few click scenarios on the root page must confirm it
(section 4).

Two other ways to make the pointer, weighed and not recommended: a redirect from `/` to
`/r/v48/` (simplest, but every address a visitor copies names a release), and a CDN rewrite of `/`
to the current release without a base address (clean addresses, but an open page would then fetch
the next release's files after a release).

### Headers

| Path | Cache-Control | Also |
| --- | --- | --- |
| `/r/<id>/*` | `public, max-age=31536000, immutable` | the right content type; compression for HTML, JSON and JavaScript |
| `/index.html` (the pointer) | `no-cache` for browsers (they ask each time and get a short "not modified" while it is current); at the CDN a short time, or until the release clears it | the content policy (section 6) |
| `/formats/*` | `public, max-age=86400` | |

Data files under `/r/` also get `Access-Control-Allow-Origin: *` once Stage 0 exists (section 5).
The CDN should ignore the query string when it looks a page up, so that `?lens=engine` and
`?lens=laws` share one cached copy of the page; the page reads the query itself.

### Addresses

Query strings first: the viewer already reads `lens`, `select`, `entry`, `species`, `run`, `part`,
`example`, `machine`, `slow` and more, and writes `select=` and `entry=` back with
`history.replaceState` (`src/ui/viewer.js`). On the site, a card's detail
(`?lens=experiments&select=card:<id>`) becomes a link that can be sent. Path-style addresses
(`/experiments/e07-v1`) need a rewrite rule that serves the page for those paths, and the base
address above; leave them until someone needs them. A link that shows its own picture and title
when it is pasted into a chat or a post needs a page per address with its own tags, made at
release or by a function at the edge; also later.

### Cost drivers (measured; no prices)

| Quantity | Value | What to look up |
| --- | --- | --- |
| Stored per release | 155.5 MB (168 MB with the frog); compressed copies add 56.5 MB (gzip) and 43.8 MB (brotli) if uploaded | price per GB-month |
| Releases | 69 in 6 days (14 to 19 November 2026), 5 to 23 a day | |
| Changed per release | 4.3 to 8.9 MB in four of the last five (Version 43 re-packed 200 files, 97 MB) | whether the store copies an object within itself without charge, so that only changed files are uploaded |
| Per first visit | about 1.0 MB with gzip, 0.75 MB with brotli, 5.15 MB if nothing is compressed; of it the site's own share (the page and the run files) is 0.85 MB with gzip, 0.61 MB with brotli, 4.46 MB raw, and three.js comes from cdnjs | price per GB of egress |
| Requests per first visit | about 10 (page, three.js, the font style sheet and font files, about five run files) | price per million requests |
| A visitor or crawler that fetches everything | 155.5 MB raw, 56.5 MB gzip, 43.8 MB brotli | whether the provider offers a hard spending cap, or only alerts |

Kept whole, every release costs 155 MB of storage: at five releases a day, as on 19 November, about
0.8 GB a day; at 23, as on 17 November, about 3.6 GB. Two ways to bound it, for the owner to choose: keep the last N releases and every
release that was announced or tagged, removing the rest after a stated time; or store each
distinct file once and map releases to files, which needs a function at the edge and is worth
building only if every release must be kept forever.

### Staging and production

A release is reachable at `https://cells.eidosoma.ai/r/<id>/` as soon as it is uploaded, before the
pointer moves. That address is the staging: the gate's looks are made there, then the pointer
moves. A separate staging name (`staging.cells.eidosoma.ai`, its own pointer over the same
releases) is optional. Release pages under `/r/` should carry `X-Robots-Tag: noindex` and point to
the root as canonical, so that search engines list one page.

---

## 3. One build, two targets

**Recommendation.** Keep one export and one staged folder. The site's release is made from that
folder by a tool that adds a document wrapper, a base address and a short host profile, and
changes nothing else; a test holds that the page inside is the artifact's page byte for byte. The
site keeps the artifact's packing of files, so its read-back is file-by-file identity, and the page
learns what its host allows from the host profile, never by looking at its own hostname.

```
npm test → npm run export → npm run stage -- --new out/publish-vN   (as today)
                                   │
                ┌──────────────────┴───────────────────┐
         the artifact: uploads              the site: tools/stage_site (new) writes
         from the staged folder             out/site-vN/r/vN/  (the files, index.html, root.html, release.json)
         (as today)                         then tools/release_site (new) uploads, checks, moves the pointer
```

### What differs between the two

| | Artifact | Site | Where it is made |
| --- | --- | --- | --- |
| Document around the page | Added by the host | `wrap()` of `tools/lib/build_page.mjs`, which already copies the host's wrapper | the site's staging |
| Addresses | `#name` only | query strings and `#name` | nothing: the viewer handles both |
| File packing | the 511-file packing | **the same** | the export, once |
| three.js | cdnjs | cdnjs at first; later, optionally, the site's own copy (below) | |
| Fonts | Google Fonts | Google Fonts at first; later, optionally, the site's own copies (section 6) | `src/page.html` |
| Base address | none | `<base href="/r/vN/">` in the root page only | the site's staging |
| Host profile | none | one small JSON block (below) | the site's staging |
| Content policy | the frame's | the site's own headers | the release tool |
| `<meta name="claude:viewport-fit-sides">` in `src/page.html` | meant for the host | ignored by browsers | nothing |

**Absolute paths.** None in the page but three: the cdnjs address of three.js, the Google Fonts
style sheet, and links out to public databases, which are the same on both hosts. `THREE_LOCAL`
(`/vendor/three.module.min.js`) is the local server's alone. Every file beside the page is fetched
by a path relative to it.

**Keep the packing.** The site could cut files more finely (no 511 limit), but every byte that
differs between the two targets is something that can drift and must be checked twice. The cuts
cost little: the frog's members' files of 6,000 proteins are 1.0 to 1.6 MB raw and 118 to 204 KB
gzipped, by `docs/XENOPUS.md`. Re-packing is worth it only where a measured visit gains, and then
it should change the export for both targets.

**How the page learns its host.** Not by its hostname, which would grow two code paths. The site's
staging writes one block into the page, and the artifact page has none:

```html
<script type="application/json" id="cells-host">
{"format": "cells.visualizer.host@1", "release": "v48", "links": "query", "api": null}
</script>
```

The viewer reads capabilities from it: `links` says whether an address with a query string can be
shared (offer "Copy a link to this view" only then), `api` where a Stage 1 service answers (none
on the artifact), `release` what to show in the page's stamp. With no block, the viewer behaves as
on the artifact today. One reader, one set of defaults, one test.

**three.js.** Two ways keep one bundle for both targets: leave it on cdnjs for both (the site's
content policy then names cdnjs), or have the bundle import the bare name `three` and let a small
**import map** (a short JSON block in the page that tells the browser which address a module's
name stands for) say where it comes from (cdnjs on the artifact, the site's own
`/vendor/three/0.170.0/` on the site). Whether the artifact's frame allows an import map is not
known and would have to be tried. Start with cdnjs for both.

### What would change in the viewer

| File | Change | Needed for |
| --- | --- | --- |
| `src/ui/viewer.js` | `setLens` writes the tab with `history.replaceState(null, "", "#" + id)`; under a `<base href>` that relative address resolves to the release's folder and would move the visitor's address. Build it from `new URL(location.href)` with only the hash set, as `writeAddress` already does. Read the host profile; offer a link to the view where `links` is `query` | the pointer page; shareable links |
| `src/lenses/protein_shelves.js`, `src/replay/source.js`, `src/ui/landing.js`, `src/lenses/machine_shape.js` | Nothing while files are addressed relative to the page and the base address is used. If a data root other than the page's folder is ever wanted, one resolver used by every loader, not one per loader | |
| `src/page.html` | The fonts' `<link>`, if the site serves its own fonts (the site's staging may rewrite that one line, held by the test) | privacy |
| `tools/lib/build_page.mjs` | `wrap()` takes the site's extra head (title, description, canonical link); an option to write the host profile; optionally minify (both targets) | the site's staging |
| `tools/stage_site.*` (new) | From the staged folder: `r/vN/index.html` (the page, wrapped), `r/vN/root.html` (the same with its base address, to become the root page), the files as they are, `release.json`, the headers for each path | releases |
| `tools/release_site.*` (new) | Upload to `r/vN/` (copying unchanged files from the previous release inside the store where the store allows it), read back, move the pointer, roll back | releases |
| `tools/check_fetches.mjs` | A mode that serves a staged site folder with compression on (or reads a live release) and records bytes as sent, beside the raw budget | the read-back |
| `tests/` | One test, run in `npm test`: the page inside the site's release equals the staged page, apart from the declared insertions; every file of the release is the staged folder's | no drift |

The standalone file (`npm run export -- --standalone`) is a third target already, and is unaffected.

---

## 4. Releases and checks

**Recommendation.** A site release rests on the same gate as an artifact publish and on the same
staged folder. Its read-back is a listing of the release's folder compared file by file with the
staged folder, plus a check of headers on one file of each kind through the CDN; only then does
the pointer move. Each release and each move of the pointer is recorded in `artifacts.json`, beside
the artifact's versions.

### A release, step by step

1. **The gate, as today** (README, "Publishing"): a clean copy of the branch's head, `npm test`,
   the click suite (`npm run check:all`), `npm run export`, `npm run stage`. For `/r/vN/` the site
   adds no gate of its own: it serves the same bytes. The root page is the one variant that
   differs (its base address changes how relative addresses resolve), so a few click scenarios
   run on it in the site's layout, served locally: a tab pressed, a card's detail opened and
   closed, a species chosen, a family opened, a still coming into view. They run before the first
   release and again whenever the viewer's address code changes.
2. **Stage the site** from that folder (`tools/stage_site`), which refuses a folder that holds
   anything the export did not list (as `tools/stage_publish.py` does) and runs the identity test.
3. **Upload** to `/r/vN/`. A release folder is written once: the tool refuses to write into a
   release that exists.
4. **Read back, before the pointer moves:**
   - list `/r/vN/` from the store, with sizes and checksums, and compare it with the staged folder:
     the same paths, the same bytes, nothing more;
   - fetch through the CDN, asking for compression, the page and one file of each kind (a run, a
     part file, shelves, members, names, a bench, a shape, a still, the cards) and check the
     status, content type, compression, cache header, cross-origin header and, for the page, the
     content policy; decompress and compare each with its staged file;
   - load `/r/vN/` and the addresses of the fetch budget with the fetch check in its site mode, and
     record bytes as sent as well as raw.
5. **Looks by eye** at `https://cells.eidosoma.ai/r/vN/` and a few addresses with query strings
   (a card's detail, a species, a run), as the publish notes record looks today.
6. **Move the pointer**: copy `/r/vN/root.html` to the root `index.html`, clear it from the CDN,
   then fetch `/` and check that it names `vN`.
7. **Record**: a `site` entry in `artifacts.json` with the release id, the date, the viewer commit,
   the engine revision the map reads, the staged folder it came from (the same folder the
   artifact's version names, when both are published), the gate, file count and bytes, the
   read-back's result, the release the pointer moved from, and what was looked at.

`release.json` in each release carries the same facts in machine-readable form, with each file's
path, format, bytes and checksum, written by the staging tool. It is also the index of Stage 0
(section 5).

### Rolling back

Copy the earlier release's `root.html` (kept in its own release folder, so a rollback needs
nothing from the release machine's disk) to the root `index.html`, clear it from the CDN, check
`/`, and record the move with its reason. Pages already open keep working: their release's files
are still there. Nothing is deleted in a rollback.

### What stays manual

The decision to release; the looks by eye; the command that moves the pointer (kept apart from the
upload, so that an upload never goes live by itself); removing old releases under the retention
rule; and the artifact publish, which stays as it is.

---

## 5. The API, in stages

**Recommendation.** Start with Stage 0: make the files the site already serves a documented,
read-only interface, with an index of what exists, a JSON Schema for each format, open
cross-origin reads and a written promise of what will not change; where a query is common, answer
it with a file built at release. Build Stage 1, a small read-only service, only when queries
outgrow such files; when it comes, prefer a service over a database file built at each release.
Stage 2, runs on request, belongs to the engine's owner, who decides first what may be run.

### Who would use it, and for what

1. **The viewer itself**: searching across species, which today would mean fetching every
   species' names file (6.8 MB raw and 1.5 MB compressed for the six species with one in Version
   47; 9.5 MB raw with the frog's).
2. **Scientists and students** who want what the viewer shows as data: a species' proteins with
   their membrane side, family and the evidence for each; the machines of a species and their
   parts; a run's recorded arrays and events, under the experiment's own names; the standing of
   each experiment as the record words it.
3. **Developers of other tools** who want to link into the viewer or show its data in their own
   pages: stable addresses, the formats and their schemas.
4. **The project's own tools and notebooks**, reading published releases instead of a checkout.
5. **Later, people who want a simulation run** (Stage 2).

Nobody outside is known to be waiting for an API today; that is the owner's to say (section 8).

### Stage 0: the files are the API

Every published file already names its format, which is versioned: `cells.visualizer.replay@1`,
`replay_part@1`, `replay_parts@1`, `species_proteins@1`, `species_protein_members@1`,
`species_protein_names@1`, `machine_bench@1`, `machine@1`, `machine-shape@1`, `assembly_run@1`,
`experiment_cards@1`; inside a replay, the engine's own `cells.run_view@1`. Each has a contract
under `schema/`. What is missing is what makes files an interface:

| Needed | Proposal |
| --- | --- |
| Stable addresses | `https://cells.eidosoma.ai/r/<release>/<path>` never changes. The root names the newest release and moves |
| An index of what exists | `/r/<release>/release.json`: every file with its path, format, bytes, checksum and where its sources are; and `/releases.json`, the list of releases with their dates |
| Cross-origin access | A browser lets a page on another site read a file only if the file's response allows it (**cross-origin** access). `Access-Control-Allow-Origin: *` on data files: they are public, need no credentials and the site uses no cookies, so the open setting is safe. Not on the pages |
| A machine-readable description | **JSON Schema** (draft 2020-12), one per format, at `/formats/<format>/<major>.schema.json`, each file's response pointing to it (`Link: <…>; rel="describedby"`). JSON Schema describes documents, which is what static files are; OpenAPI describes operations (paths, parameters, responses) and since version 3.1 uses JSON Schema 2020-12 as it is. So the schemas are written once now, and Stage 1's OpenAPI description refers to the same files |
| A promise about change | Below |

**The promise**, for the owner to adopt or change:

- A release's files never change and are not removed while the release is kept (the retention
  rule says how long).
- Within a format's major version (`@1`), changes only add: new optional fields, new values a
  reader can ignore. Readers must ignore what they do not know.
- Removing or renaming a field, or changing its meaning or unit, is a new major (`@2`), recorded in
  a list of changes, announced in the index, and kept beside the old one for a stated time.
- **Formats are promised; the cutting of files is not.** Names such as `members-03.json` and
  `.parts-2.json` exist because of the artifact's 511 files, and the frog's were cut differently
  for that reason. A reader finds files through the index and the shelves' own `file` and `at`, not
  by guessing names.
- These are the viewer's formats, shaped for drawing (members as rows of columns, quantised arrays
  marked `quantised` that the viewer never prints as numbers). If outside users need a shape of
  their own, publish a separate dataset format then, rather than freezing the viewer's.

**Licences and attribution.** The rule of `tests/licence_classes.test.mjs` already holds every data
record: only permissive sources stand behind a value; a non-commercial source or one with no stated
terms is a pointer in words, never data. The API must carry attribution with the data, and today
only some files carry their sources:

| Carries its `sources` | Does not; where its sources are |
| --- | --- |
| a species' `shelves.json`; a machine's file; the assembly's runs | members' and names files (their species' `shelves.json`); benches (the catalogue's core, inside the page's scene); shapes (the catalogue's sources, from the Protein Data Bank entry each names); runs and parts (Cells' own runs: the project's own terms); `cards.json` (the project's own record) |

So Stage 0 needs, for each file without its own sources, a pointer to the file that holds them
(in the index, and in the file where its format allows an added field), and a stated licence for
the project's own data (runs, cards, shapes, the catalogue's words). Three things the licence test
holds for the page are for the owner to confirm before the data is offered for reuse: the ruling
that a value read from an open database stands on that database's terms even where a restricted
tool computed it (D178); the decision of 18 November 2026 on CDD, which states no terms; and
NCBIfam's share-alike licence, which may require that what is derived from it be offered under the
same terms. The test calls its ruling "the project's rule and not a legal opinion".

**Example.**

```
GET /r/v48/proteins/human/shelves.json
Accept-Encoding: br, gzip

200 OK
Content-Type: application/json
Content-Encoding: br
Cache-Control: public, max-age=31536000, immutable
Access-Control-Allow-Origin: *
Link: </formats/cells.visualizer.species_proteins/1.schema.json>; rel="describedby"

{"format": "cells.visualizer.species_proteins@1", "species": "human", …,
 "sources": [{"name": "UniProt", "release": "2026_04", "licence": "CC BY 4.0",
              "class": "permissive", "cite": "The UniProt Consortium, …", …}, …]}
```

**Limits and abuse.** Static files behind a CDN need little: the CDN absorbs load, and files that
never change are served from its cache. A crawler that takes everything costs 44 to 56 MB of
egress a release if compression is on; publishing one archive of each release for bulk users
(compressed, about that size) is cheaper for everyone than 459 requests. A per-address request
limit at the CDN, set high, guards against a runaway client.

**Answers built at release.** Many of the queries a service would answer are fixed for a release
and are files already, or can be: a family's members are reached through its shelves' `file` and
`at` (19,594 families across the six species that have families in Version 47); the runs of an
experiment are in the scene's catalogue; a machine's parts are in its bench. What is missing is a
search across species: an index cut by the first letters of a gene, a name or an accession, some
hundreds to a few thousand small files, so that a search fetches a few kilobytes and not 1.5 MB
of names files. On
the artifact such files would press on the 511 limit; on the site they cost nothing but storage. A tool that cuts a search index into small files for a static site
exists (Pagefind is an example of the kind); the names files' own rows would be the input.

### Stage 1: a small read-only service

**When.** When a query cannot be answered by a file made at release: free text across all species
with ranking, combined filters (a side, a family and an evidence level at once), or paging through
results whose order the caller chooses. A threshold to watch: when the files one search needs
grow past a few hundred kilobytes compressed (the names files alone are 1.5 MB today, 2 MB with
the frog), or when the questions asked combine filters that cannot be listed ahead of time, a
service is cheaper to keep correct than more files.

**Resources** (all `GET`, all read-only, under `/api/v1/`):

| Resource | Answers |
| --- | --- |
| `/api/v1/releases` | the releases, newest first |
| `/api/v1/species` | each species: its counts, shelves and sources |
| `/api/v1/proteins?q=&species=&side=&family=&limit=&after=` | search and filter across species, paged |
| `/api/v1/species/{species}/families/{family}` | a family and its members, paged |
| `/api/v1/machines?species=` and `/api/v1/machines/{species}/{machine}` | a bench, a machine and its parts with their proteins |
| `/api/v1/experiments` and `/api/v1/experiments/{id}/runs` | experiments with their standing, and their runs, linking to the run files |

Every answer names the release it was read from; `release=` pins one. Paging is by a cursor
(`after=`), with a largest page (for example 100).

**Example** (the row is the human file's own).

```
GET /api/v1/proteins?q=KCNJ2&species=human&limit=20

200 OK
Content-Type: application/json
Cache-Control: public, max-age=300
Access-Control-Allow-Origin: *

{"format": "cells.api.protein_search@1", "release": "v48",
 "query": {"q": "KCNJ2", "species": ["human"], "limit": 20},
 "results": [{"species": "human", "id": "P63252", "gene": "KCNJ2",
              "label": "Inward rectifier potassium channel 2", "side": "in",
              "family": "IPR003271", "units": ["U19"],
              "file": "/r/v48/proteins/human/members-05.json"}],
 "next": null,
 "sources": [{"name": "UniProt", "licence": "CC BY 4.0", "cite": "…", "url": "https://www.uniprot.org/"}, …]}
```

**The options.**

| | Functions at the edge over prebuilt indexes | A small service over a database file built at release | A conventional server with a database |
| --- | --- | --- | --- |
| What it is | Short functions the CDN runs near the visitor, reading index files the release wrote | A small program answering from one read-only database file (SQLite with its full-text search is an example), built by the release tool from the same files and published with the release; Datasette is an example of a ready-made server of the kind | A server process and a database server kept running, loaded from the files |
| To run | Billed per call; no machine | One small machine or a container that sleeps when idle | A machine and a database to keep up, back up and patch |
| To keep correct | The indexes are files of the release, checked like the others; the logic is small but spread over a runtime of the provider's | The database is a file of the release, its contents compared with the files by a test; one release, one database, nothing to migrate | Migrations, loading, drift between the database and the release |
| Good for | Lookups and simple filters | Full-text search, combined filters, paging | Writes: accounts, saved views, runs on request |
| Ties to a provider | Strong | Weak | Weak |

**Recommendation for Stage 1:** the small service over a database file built at each release. It is
correct by construction (the database is made from the release's files and published with them),
it has nothing to migrate, and moving it between providers is moving a container and a file. The
conventional server is for Stage 2, when something has to be written.

**How the viewer uses it, and still works without it.** The viewer asks the service only where the
host profile names one (`api`), and falls back to what it does today when the profile names none or
the service does not answer: the names file of the species shown. The artifact's frame very likely
does not let the page call another site (the local copy of its policy allows connections to the
page's own origin only; the real frame's policy has not been read), so on the artifact the page
keeps its files and its own search, as now.

**Versioning, limits, licences.** The path carries the API's major (`/api/v1/`); responses carry a
format like the files; the same promise as Stage 0. Answers are cached at the CDN by their full
address; a per-address rate limit (a token bucket at the CDN or the service: so many requests a
minute, then `429 Too Many Requests` with `Retry-After`); a largest page size, a longest query,
no regular expressions; a timeout on every query. Each response carries the sources behind its
rows, and nothing from a non-commercial source, or one with no stated terms, is served as data,
exactly as the test holds the files.

### Stage 2: runs on request

Not designed here; this is what it would need and what must be decided first.

**What it needs.** An identity for every caller (no anonymous computing), with a quota each. A
queue of jobs, and workers that run the engine out of process as the project's detached jobs do
today, each in its own unit with a memory cap, a processor share and a time limit, and the engine's
own jobs on the graphics card first. A request names a published experiment definition and values
for a stated list of its parameters, never code, and is validated against a schema before it is
queued. Limits on world size, simulated time and wall time. Each run recorded as the project
records runs: the engine's revision, any uncommitted change and the frozen snapshot. The run view
(`cells.run_view@1`, written by `src/cells/records/run_view.py`) as the contract between the engine
and the viewer, and the packaging the viewer already reads. Endpoints to follow a job (queued,
running, finished, failed, with its log) and to fetch its saved view. Storage with a retention
rule. Cost control: a global cap on concurrent runs, a daily budget, and a switch that stops new
jobs. Workers with no outbound network.

**What the engine's owner decides first.** Which models and experiments may be run on request, and
which of their parameters; whether runs on request use the project's machines or rented ones;
how such a run is labelled (presumably a development run, not judged, in the viewer's ladder of
words); whether its results are public; who may run, and how much. The run-view writer's first
version covers one model family (`resolved_pump_composite@1` over `resolved_pump_tissue@3`, and
`resolved_pump_tissue@3` alone) and refuses the others, so the families offered are bounded by
what it can write.

**A sketch, for illustration only** (names and fields are placeholders, not a design):

| Resource | Does |
| --- | --- |
| `POST /api/v1/runs` | asks for a run: an experiment definition and values for its offered parameters; answers `202 Accepted` with the job's address |
| `GET /api/v1/runs/{job}` | the job's state (queued, running, finished, failed), its place in the queue, its limits and, once finished, its run's address |
| `GET /api/v1/runs/{job}/view` | the saved run view, in the packaged form the viewer reads |

```
POST /api/v1/runs
Authorization: Bearer <a key issued to the caller>
{"experiment": "<a published definition>", "parameters": {"<name>": <value>}}

202 Accepted
Location: /api/v1/runs/<job>
{"format": "cells.api.run_job@1", "job": "<job>", "state": "queued",
 "limits": {"wall_s": …, "memory": "…"}, "engine_revision": "…"}
```

Versioning: the run view's own format (`cells.run_view@1`, and the viewer's packaging of it) is the
contract; the API's major is in its path. Limits: a quota per key, a cap on runs at once and in
the queue, a ceiling on what one run may use. Licences: a run is the project's own output, offered
under the licence the owner chooses for the project's data (section 8), and any value it carries
from a source keeps that source's terms.

---

## 6. Security and privacy

**In brief.** The site would hold no secrets and the repository none of its credentials; only the
release machine would upload, and moving the pointer would be a separate step. The site would set
a strict content policy of its own, open its data to other sites for reading only, count visits
from its own logs without identifying visitors, and be protected from a spike by caching and by
limits on the API.

- **No secrets in the repository.** Upload credentials live on the release machine (or in a
  secret store), never in a file that is committed. Prefer short-lived credentials issued per
  release over long-lived keys. The repository is public: if releases are ever made by continuous
  integration, credentials must never reach builds of outside pull requests.
- **Who can deploy.** The owner, and whoever the owner names. Split the rights: one may write new
  release folders and cannot delete; one may write the pointer; deleting old releases is a third,
  used rarely. Turn on the store's own versioning or deletion protection for `/r/`.
- **Cross-origin rules.** `Access-Control-Allow-Origin: *` on data files and the API's answers,
  which need no credentials; nothing on the pages; no cookies anywhere.
- **Content policy** (a `Content-Security-Policy` header: the list of places a page may load
  scripts, styles, pictures and data from, which the browser enforces; the site's own, stricter
  than the frame's):
  `default-src 'none'`; scripts from the site itself, plus a hash of each inline script computed
  by the staging tool for each release (the boot script and the viewer's module; the JSON blocks
  are not run and need none), plus cdnjs while three.js comes from there; styles from the site and
  inline (the viewer sets style attributes); images from the site and `data:`/`blob:`; connections
  to the site and the API; no workers (the viewer starts none); fonts from the site (or Google's,
  while used); `frame-ancestors 'self'`
  unless other sites may embed the viewer (a question for the owner); `base-uri 'self'`. Also
  `Strict-Transport-Security`, `X-Content-Type-Options: nosniff`, `Referrer-Policy:
  strict-origin-when-cross-origin`, and a `Permissions-Policy` that turns off camera, microphone
  and location.
- **Other parties.** Every visit today asks cdnjs for three.js and Google for the fonts, which
  tells both of the visit. The site can serve both itself: three.js from `node_modules` (MIT
  licence, pinned at 0.170.0); the fonts from their own releases, after confirming their licences
  allow it (both are, as far as is known, under the SIL Open Font License). Then a visit asks
  nobody else.
- **Counting visits without tracking.** No cookies, no scripts of others, no identifiers. Count
  requests for the page and for each kind of file from the CDN's logs, with addresses of visitors
  shortened or dropped and the logs kept for a short, stated time. If more is wanted, a counter
  that keeps no identifiers and sets no cookies (GoatCounter and Plausible are examples of the
  kind), served from the site. The viewer's one use of the browser's storage (the landing's opened
  bands) stays in the browser and is never sent.
- **A spike.** The files never change, so after the first request the CDN answers from its
  cache and the store sees little. The cost is egress: a first visit is about 1 MB compressed, so
  the bill grows with visits, not with requests to the store. Set budget alerts, and a hard cap if
  the provider has one (look it up: an alert alone does not stop the spending). The API:
  per-address limits, answers
  cached at the CDN, a ceiling on concurrent queries, and a switch that turns it off while the site
  and its files keep working.

---

## 7. A plan in steps

Each step can be done and checked on its own. The sizes of work are rough estimates.

| Step | What | Needs from the owner | Work | Checked by |
| --- | --- | --- | --- | --- |
| 1 | Choose the kind of hosting and a provider; set the retention rule and the release names | decisions (section 8) | | |
| 2 | Open the account; storage, CDN and certificate for `cells.eidosoma.ai`; serve a placeholder page | the provider's account; control of the domain's DNS | half a day | the address answers over HTTPS with the intended headers |
| 3 | The site's staging tool, the host profile and the change to `src/ui/viewer.js`; the identity test; a local server of the staged site with compression on | | about a day | `npm test`; the page at `/` and at `/r/vN/` locally, its fetches |
| 4 | The release tool: upload, read-back, pointer, rollback | credentials scoped as in section 6 | about a day | a test release to a scratch prefix, rolled back |
| 5 | The first release, from the next staged folder; record it in `artifacts.json` | the approval to make it public (or unlisted first) | an hour, after the gate | the read-back, the looks, `/` names it |
| 6 | The fetch check's site mode: bytes as sent | | half a day | its record beside the raw budget |
| 7 | Headers hardened: content policy with hashes; three.js and the fonts from the site (if chosen); minifying the code (both targets) | decisions on other parties | about a day | the policy reports nothing in the click suite; the fetch check |
| 8 | Stage 0: `release.json` as the index, `releases.json`, schemas for the formats most asked for first (species' proteins, members, benches, replays), cross-origin headers, a page that documents them and states the promise and the licences | the promise; the data licence; the licence questions | two to four days | each published file validates against its schema in `npm test` |
| 9 | Answers built at release (a search index cut into small files, a family's members, a machine's parts), if a user asks | a user's need | about two days | sizes and fetches measured |
| 10 | Stage 1, if the measures say so | a decision; where it runs | about a week | answers compared with the files, release by release |
| 11 | Stage 2 | the engine owner's decisions first | not estimated | |

**Left for later on purpose:** path-style addresses and link previews per card; storing each
distinct file once across releases; a binary packaging of runs; re-cutting files for the site
only; analytics beyond log counts; anything that writes.

---

## 8. Questions only the owner can answer

They were answered on 19 November 2026: section 9.

1. Which is the public face: the site, the artifact, or both? Should the site open publicly at
   once, or unlisted while it is tried?
2. Which provider, under whose account, and who may release and move the pointer?
3. Should every release stay reachable forever, or the last N and the announced ones?
4. Should the site serve three.js and the fonts itself, so that a visit asks nobody else, at the
   cost of one line that differs from the artifact's page?
5. Under what licence does the project offer its own published data (runs, cards, shapes, the
   catalogue's words)? Do the ruling on values read through open databases (D178), the decision on
   CDD and NCBIfam's share-alike terms extend to offering the data for reuse through an API?
6. Who is the API for first: the viewer alone, or outside users the owner has in mind?
7. Visits counted from the CDN's logs only, or a counter that keeps no identifiers?
8. May other sites embed the viewer in a frame?
9. What spending ceiling, per month, should stop the site's or the API's growth?
10. For the engine's owner: may runs ever be started on request, and if so, which?

## What could not be determined

- Whether the artifact host compresses what it serves, and what the real frame's content policy
  is: neither was read (the local policy is an approximation).
- What the Machines, Proteins, Engine and Laws tabs fetch on a first visit, measured in a browser:
  those rows come from the code and file sizes. Font requests were not measured.
- The frog's fetches in a browser. Its release was measured after this review was written (above).
- Traffic, and every price: no figure here is a cost.
- Each provider's limits (file sizes it compresses, files per deploy, spending caps): to be looked
  up against the quantities above.


---

## 9. What the owner decided (19 November 2026), and what follows

The owner answered the ten questions of section 8 on the day of the review, and three points that
were left open (how many releases the site keeps, the public data's licence, the cost of visits)
later the same day. Each answer is given here in plain words, with what it changes.

| | Decided | What it changes |
| --- | --- | --- |
| 1 | The site will be the public face. Nothing is public yet; the artifact stays the working copy, published as before | The artifact and the site are both kept; the site is what others are sent to |
| 2 | The site is served from a machine of the project's own, in a container, and the owner sets that up | Option C of section 2, not A: no object storage and no upload. A release is a folder on that machine's disk, and the server compresses and sets headers itself |
| 3 | Releases are marked by tags in the repository, and the site keeps three releases | The site does not keep every release. It keeps the current one and the two before it, for pages that are open and for rolling back |
| 4 | The site serves three.js and the fonts itself | A visit to the site asks no other party. The artifact keeps cdnjs and Google Fonts, the only places its frame allows |
| 5 | The demonstration data is public, under a Creative Commons licence. Private data will come later and will not be public | Two classes of data, never in one folder (below). The public data's licence is taken as CC BY 4.0, the Creative Commons Attribution licence, unless the owner names another; whatever is read from a source keeps that source's own terms and its attribution (section 5, "Licences and attribution") |
| 6 | The API's only user, for now, is the viewer | Stage 0 without its public side: the index is still made, because the release and its check need it; the schemas, the written promise and open cross-origin reads wait for an outside user |
| 7 | Visits are counted from the server's own logs, and perhaps with a counter that keeps no identifiers | No cookies and no identifiers, as section 6 has it |
| 8 | Other sites may show the viewer in a frame | The site's content policy does not limit who may frame it |
| 9 | Nothing is to be spent on services for other users; the marginal cost of visits is not a concern | No paid service stands in front of the site. What the machine's own provider bills for outgoing traffic grows with visits (a first visit sends about 1 MB compressed, section 2), and is accepted |
| 10 | No runs on request yet; later, behind a login | Stage 2 waits for a login, which the private data needs as well |
| 11 | Nothing on the machine terminates HTTPS (said the same evening) | The server obtains and renews its own certificate: the example's `https` form (`deploy/`). The domain's DNS must point at the machine, and the machine's own firewall and its provider's must admit ports 80 and 443, before the certificate can be issued |

### The layout on the machine

The layout of section 2 stands, with a folder on disk where it had a store:

```
<site>/index.html          the pointer: a copy of the current release's root.html
<site>/r/v49/…             the current release: the page, its files, three.js and the fonts, release.json
<site>/r/v48/…             the release before, unchanged, until the retention rule removes it
```

The container serves `<site>` and nothing else, read-only. A release is made in three steps that
stay apart: the release folder is written beside the others (a folder that exists is never
written into); it is read back through the server (every file's bytes against the staged folder,
and the headers of one file of each kind); only then is the pointer copied into place. Rolling
back is copying an older release's `root.html` over the pointer, as section 4 has it, for as long
as that release is kept.

### Tags, and what a tag can and cannot give back

Each published version is tagged `viewer-vNN`, an annotated tag on the commit that records the
version in `artifacts.json`; `viewer-v48` is the first. **A tag marks the viewer's code and its
record, not a folder that can be rebuilt from the repository alone:** the run files are made from
the engine's saved evidence, which is not in git (section 2, "One fact shapes every option"). So
going back to a release the site no longer keeps means staging it again, on a machine that has
that evidence, from the tag's code. If that should ever be needed without the evidence, the
release folders themselves would have to be kept somewhere, which is a decision for then.

### Public and private data

Everything the artifact and the site serve today is the public demonstration data. Private data,
when it comes, needs three things this design does not have yet, and they are not built now:

- a login, and a server that checks it before it sends a private file: a static file server
  cannot (so Stage 1's small service, or the server's own access rules, would hold that door);
- a folder of its own, outside the public release folder, with its own catalogue: the public
  export lists every file it publishes by name (`out/cells-architecture.files.json`), and a
  release refuses any file the export did not list, so a private file cannot enter a public
  release by standing in the wrong folder;
- its own rule in the licence test, which today knows one class of published data.

Until then the rule is the simple one: nothing private is staged, and the public folder holds only
what the public export lists.

### What the server must do (for whoever sets up the container)

These are properties, not a product; any static file server that can do them will serve.

- Serve the site folder read-only, and nothing else of the machine. No secret, key or
  credential inside the container or the folder.
- Compress HTML, JSON, JavaScript and font style sheets as it sends them, or serve compressed
  copies the release wrote beside the files. The largest file is the page, 5.1 MB.
- Headers as in section 2: files under `/r/` cached for a year and marked immutable; the pointer
  page revalidated on every visit.
- A content policy as in section 6, without a limit on framing, and with scripts and fonts from
  the site itself.
- Logs without visitors' full addresses kept past a short, stated time.
- Limits of its own: a cap on memory and processors, so that the site cannot take them from the
  project's own jobs on the same machine, and a limit on requests from one address.
- HTTPS for `cells.eidosoma.ai`, with the certificate renewed by the server or a proxy before it.

A machine that also holds the project's working files is a larger thing to expose than a rented
static host: the container's isolation, the read-only folder and prompt updates of the server
are what stand between the two. A caching proxy in front of the machine would also hide its
address and absorb a spike; whether to use one is the owner's choice, and nothing here needs it.

### The plan, as it now stands

| Step | What | Who |
| --- | --- | --- |
| 1 | The site's staging tool: from the staged folder, one release folder with the page wrapped, its `root.html`, the files, three.js and the fonts beside them, and `release.json`; the test that the page inside is the artifact's page but for the declared lines | the viewer's side |
| 2 | The one change in `src/ui/viewer.js` (section 3) and the host profile | the viewer's side |
| 3 | An example container and server configuration that does what the list above asks, in the repository, for the owner to run or replace | the viewer's side writes it; the owner runs it |
| 4 | The machine, the container, the domain's DNS and the certificate | the owner |
| 5 | The release steps on that machine (write, read back, move the pointer), the record in `artifacts.json`, the tag | the viewer's side, once step 4 stands |
| 6 | The fetch check's site mode: bytes as sent | the viewer's side |
| Later | A login and private data; Stage 1; a visit counter; runs on request | decided then |

---

## 10. What is built (19 November 2026)

Steps 1 to 3 of the plan above, and the local half of step 6. Nothing is deployed, and nothing touches DNS,
certificates or accounts.

- **`tools/stage_site.mjs`** makes a release folder from the folder staged for the artifact, which it only reads. It
  writes `<site>/r/<id>/` once: a folder that exists is refused, and a new one is written under a hidden name and
  moved into place whole. The release holds:
  - `index.html`: the staged page in the artifact host's wrapper (`wrap`), with `lang`, a title, a description, the
    root as canonical and the host profile;
  - `root.html`: the same with `<base href="/r/<id>/">`;
  - the staged files at the same paths, the same bytes (the `upload-N.json` lists are left out; a file the export
    does not publish is refused, and `--files` holds the folder to the export's own list);
  - `vendor/three/<version>/` (from `node_modules`, at the version the page names) and `vendor/fonts/`;
  - `release.json`;
  - with `--compress`, `.br` and `.gz` copies.

  Two rewrites are counted. Every occurrence of three.js's cdnjs address becomes the release's own copy, and the tool
  stops unless the count equals the imports in the page's module script (8 on Version 49). The one Google Fonts link
  becomes the release's sheet, and the tool stops unless every family and weight it asks for has a face there. The test
  holds that undoing both gives back the staged page byte for byte. `--release` moves the pointer: the release's
  `root.html` over `index.html`, with its compressed copies beside it where the release has them, so that the page
  every visitor opens first is sent as small as the rest. `--retain 3` (`--remove`) lists, or removes, the releases
  beyond the newest three, never the pointer's.
- **The viewer.** `setLens` writes the tab's name onto the page's own address (`new URL(location.href)`), so that under
  the root page's base address a press keeps the visitor at `/`. The host profile is read by `src/core/host.js` into
  `viewer.host`, with the artifact's defaults where a page has none; nothing new is shown by it yet. A search of the
  viewer found no other address that a base address moves.
- **The fonts**, under `vendor/fonts/`: Inter 4.1 (its three static web files for 400, 500 and 600, 340,428 bytes) and
  Space Grotesk 2.0.0 (its variable file for 300 to 700, 49,256 bytes). Each is taken unmodified from its family's
  release archive, under the SIL Open Font License 1.1, whose text stands beside it. The archives are kept, with a
  manifest each, in the project's data folder outside the repository; `vendor/fonts/fonts.css` names each file's source.
- **`tools/check_site.mjs`** is the acceptance check. It serves a site folder on 127.0.0.1 as the example server does,
  opens the root page and `/r/<id>/` at three addresses each in headless Chrome, and holds five things: no request to
  another host, no missing file, no console error, the host profile read, and a tab press that keeps the address. It
  records bytes as sent beside raw.
- **What the site says of itself** (20 November 2026, for Version 53). Each release's `index.html` and `root.html` carry,
  from the About words the staged page carries (`data/site/about.json`, which the staging holds equal to the tracked file),
  a title and a description; `https://cells.eidosoma.ai/` as canonical (`SITE` in `tools/stage_site.mjs`, the one place the
  address is stated); link-preview tags with the release's own `share.jpg` (1200 by 630, the page's scene with no words);
  structured data for the site and its source code, whose one name is Eidosoma, an organisation, as the site's publisher
  and the code's author; and the About text as HTML ahead of the page for a reader with no script (the source code linked,
  its licence not), put away once the page has drawn. Each release holds `robots.txt` (everything allowed, `/r/` never
  closed, the sitemap named), `sitemap.xml` (the root) and `llms.txt` (the site for an agent); `--release` writes those three
  at the site's root before the pointer, each beside and moved into place, and removes them where a release has none.
  `tools/check_site.mjs` holds each of them, on both pages.
- **`deploy/`** is an example container (Caddy with a rate-limit module, in two forms: behind a proxy, or with its own
  certificate). It has not been validated or started.
- **`tests/stage_site.test.mjs`** runs in `npm test`, in about a second.

**Measured on Version 49** (the staged folder of the artifact's Version 49, staged with `--compress`, 121 s):

- The release holds 478 files and 174.9 MB; the copies add 45.6 MB (brotli) and 58.8 MB (gzip).
- A first visit to the root page's opening view makes 11 requests, all to the site: 6.18 MB raw, and 1.33 MB as sent
  while the pointer had no compressed copy and went out gzipped as it was sent. The pointer step now moves the
  release's copies with the pointer. Measured again so, on a trial release staged from the head the same day (the
  page 5.15 MB with the frog's life stages): 11 requests, all to the site, 6.24 MB raw and 1.05 MB as sent, the
  pointer 613 kB of it as its brotli copy.
- The fonts are 275 kB of that, sent as they are: woff2 does not compress further.
- The page of Version 49 predates the change to `setLens`, so on its root page a tab press still moves the address
  into `/r/v49/`, and its viewer reads no profile (9 of the check's 42 checks). A release staged from a page exported
  with this round's viewer passes all 42.

**A release, step by step:**

1. **Stage.** Run the gate and `npm run stage -- --new out/publish-vNN` as for the artifact. Then run
   `node tools/stage_site.mjs --staged out/publish-vNN --site SITE --id vNN --compress --files out/cells-architecture.files.json`.
2. **Check.** Run `node tools/check_site.mjs --site SITE --id vNN` (45 s). On the server, read
   `/r/vNN/` back and check the headers of one file of each kind.
3. **Pointer.** Run `node tools/stage_site.mjs --site SITE --id vNN --release`, which checks the release against its
   `release.json` first and says which release it left. A rollback is the same command with an older id.
4. **Record** a `site` entry in `artifacts.json`: the id, the date, the commit, the engine revision, the staged folder,
   the check's result and the release the pointer left.
5. **Tag** the recording commit `viewer-vNN` and push the tag. Then `--retain 3 --remove`.

**Still the owner's:** the machine, the container (from `deploy/` or another server, in the form with its own
certificate: decision 11), pinning the images, DNS, opening the ports, and making the site public. **Still open:** the
content policy allows inline scripts, and the hashes that would replace that are in each `release.json` but not sent.
The fonts are whole files, every script each family covers. Google Fonts sends subsets cut by script, but the checks'
logs hold no sizes for them, so the two are not compared. No font tool is installed to cut the files.
