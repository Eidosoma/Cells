# The viewer's site server: Caddy with the rate_limit module built in (deploy/README.md). An example the owner may
# replace; never built or started by the repository's tools. Pin CADDY_VERSION and the module to exact releases (and
# the images to their digests) before the first build.
ARG CADDY_VERSION=2.10
FROM caddy:${CADDY_VERSION}-builder AS build
RUN xcaddy build --with github.com/mholt/caddy-ratelimit

FROM caddy:${CADDY_VERSION}-alpine
# FORM is http (behind a proxy that terminates HTTPS) or https (the server obtains its own certificate).
ARG FORM=http
COPY --from=build /usr/bin/caddy /usr/bin/caddy
COPY caddy/site.caddy /etc/caddy/site.caddy
COPY caddy/Caddyfile.${FORM} /etc/caddy/Caddyfile
