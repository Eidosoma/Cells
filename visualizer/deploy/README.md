# The site's server: an example

An example of the container that serves the viewer's site at `cells.eidosoma.ai`, for the owner to run or replace
(`docs/HOSTING_AND_API.md`, sections 9 and 10). The repository's tools never build or start it.

**Unvalidated.** Caddy is not installed where this was written, and nothing was built or started to check it:
`compose.yaml` was read as YAML and nothing more. The Caddyfiles have not been parsed by Caddy.

The server is **Caddy 2**, chosen as an example. The stock image does two of the three things asked of it: it sends
precompressed copies (`precompressed br gzip`) and it obtains and renews its own certificate. It has **no request
limit**. `Dockerfile` therefore builds Caddy with the third-party `rate_limit` module
(`github.com/mholt/caddy-ratelimit`). The other way is to drop the `rate_limit` block and set the limit in the proxy in
front. Any static file server that does what section 9 lists will serve as well.

| File | What it is |
| --- | --- |
| `caddy/site.caddy` | What the server does, in both forms: the folder, the headers, the cache rules, the logs, the limit and the files |
| `caddy/Caddyfile.http` | Plain HTTP behind a proxy that terminates HTTPS |
| `caddy/Caddyfile.https` | The server obtaining its own certificate for `cells.eidosoma.ai` |
| `Dockerfile` | Caddy with the rate-limit module; the form's Caddyfile copied in |
| `compose.yaml` | The container: its limits, its one mount, and the two forms as two profiles |

## What it does (section 9, "What the server must do")

- **The site folder, read-only, and nothing else of the machine.** `CELLS_SITE` names the folder that
  `tools/stage_site.mjs` writes. It is mounted read-only at `/srv/site`. The server's own state (certificates) and its
  logs go in Docker volumes of their own. No secret is in the folder or the image; the https form's only setting is the
  address the certificate authority writes to (`ACME_EMAIL`).
- **Compression.** A release's `.br` and `.gz` copies (`--compress`) are sent as they are where the request accepts
  them, and so are **the pointer's**: moving the pointer copies the release's `root.html.br` and `root.html.gz`
  beside it. Anything without a copy is compressed as it is sent (`encode gzip`).
- **Cache headers.** `/r/*` is `public, max-age=31536000, immutable` and `noindex`. The pointer (`/`, `/index.html`) is
  `no-cache`, so it is asked for again on every visit.
- **The content policy.** Scripts, styles, fonts, pictures and connections come from the site itself, with no
  `frame-ancestors`, so other sites may frame the viewer. The line is the one `sitePolicy()` in `tools/stage_site.mjs`
  states, and `tests/stage_site.test.mjs` holds the two equal. Inline scripts are allowed because the page carries its
  script inside it. Each release's `release.json` names its two inline scripts by their SHA-256, for a policy that would
  allow only those (`inline_scripts`).
- **A request limit**: 600 requests a minute from one address, then `429` with `Retry-After` (a first visit makes about
  fifteen). Only `GET` and `HEAD` are answered, and nothing hidden is served.
- **Logs.** One JSON line per request in `/var/log/caddy/access.log`, for counting visits. The visitor's address is cut
  to its first 16 bits (IPv4) or 32 bits (IPv6) before it is written, and the logs are kept at most 30 days.
- **Its share of the machine**: 4 GB with no swap beyond it, processors 12-15 and 28-31 (the engine's jobs hold the
  others), no graphics card. The root file system is read-only and `/tmp` holds nothing; all capabilities are dropped
  except binding ports 80 and 443.

## The two forms, and the lines that differ

The owner said on 19 November 2026 that nothing on the machine terminates HTTPS, so **the form to use is the
server's own certificate** (`--profile https`). The form behind a proxy is kept for a machine that has one. They share
`site.caddy` and the `x-site` block of `compose.yaml` whole. Only these lines differ:

| | Behind a proxy (`--profile http`) | Its own certificate (`--profile https`) |
| --- | --- | --- |
| Caddyfile, global options | `auto_https off`; `servers { trusted_proxies static private_ranges }` (the visitor's address is the one the proxy forwards) | `email {$ACME_EMAIL}` |
| Caddyfile, the site's address | `:80` | `cells.eidosoma.ai` |
| Caddyfile, in the site | none | `header Strict-Transport-Security "max-age=31536000"` (behind a proxy, the proxy sends it) |
| `compose.yaml`, the service | `site-http`; `ports: ["127.0.0.1:8080:80"]`, so only the proxy on this machine reaches it | `site-https`; `ports: ["80:80", "443:443", "443:443/udp"]` and `ACME_EMAIL` |
| `Dockerfile` | `FORM=http` | `FORM=https` |

## Running it (the owner)

1. Stage a release into the site folder and move the pointer (`docs/HOSTING_AND_API.md`, section 10):
   `node tools/stage_site.mjs --staged out/publish-vNN --site SITE --id vNN --compress`, then
   `node tools/check_site.mjs --site SITE --id vNN`, then `node tools/stage_site.mjs --site SITE --id vNN --release`.
2. With its own certificate, the form decided: point the domain's DNS at the machine's public address (a fixed
   one, so that it does not change when the machine restarts), and admit ports 80 and 443 (TCP, and UDP 443 for
   HTTP/3) in the machine's own firewall and in its provider's firewall rules. The certificate is issued only once
   both hold. Then `CELLS_SITE=SITE ACME_EMAIL=… docker compose --profile https up -d --build`.
   Behind a proxy instead: `CELLS_SITE=SITE docker compose --profile http up -d --build`, and point the proxy at
   `127.0.0.1:8080`.
3. Check what the server sends, at the site's own address (`https://cells.eidosoma.ai`; behind a proxy,
   `http://127.0.0.1:8080`): `curl -sI ADDRESS/` (no `Content-Encoding` without `Accept-Encoding`;
   `Cache-Control: no-cache`) and
   `curl -sI -H 'Accept-Encoding: br' ADDRESS/r/vNN/index.html` (`Content-Encoding: br`, `immutable`).
4. Later releases need no restart. A release folder is written beside the others under a hidden name and moved into
   place whole, and so is the pointer, so the server sees either the old or the new, never half of one.
