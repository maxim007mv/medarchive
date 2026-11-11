# syntax=docker/dockerfile:1
# Pinned Node 22 alpine without npm/yarn/corepack (OPS-05). The library image still ships
# vulnerable npm deps; the web runtime and the Trivy "base" check use this cleaned image (D-004).
ARG NODE_DIGEST=sha256:0e1754758c2df4cfa3e68d59e2e1b7374bb7fd9ea6328eaaacf15cc934af8202
FROM node:22-alpine@${NODE_DIGEST}
RUN rm -rf /usr/local/lib/node_modules /opt/yarn-* \
  /usr/local/bin/npm /usr/local/bin/npx /usr/local/bin/corepack \
  /usr/local/bin/yarn /usr/local/bin/yarnpkg
