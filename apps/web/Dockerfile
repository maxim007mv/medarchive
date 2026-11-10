# syntax=docker/dockerfile:1
# Build context is the repository root: the pnpm lockfile and workspace live there.
FROM node:22-alpine AS build
ENV COREPACK_ENABLE_DOWNLOAD_PROMPT=0 NEXT_TELEMETRY_DISABLED=1
RUN corepack enable
WORKDIR /app
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY apps/web/package.json apps/web/
COPY e2e/package.json e2e/
RUN pnpm install --frozen-lockfile --filter web
COPY apps/web apps/web
ARG API_ORIGIN=http://api:8000
RUN API_ORIGIN="$API_ORIGIN" pnpm --filter web build

FROM node:22-alpine
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 HOSTNAME=0.0.0.0 PORT=3000
WORKDIR /app
COPY --from=build /app/apps/web/.next/standalone ./
COPY --from=build /app/apps/web/.next/static apps/web/.next/static
USER node
EXPOSE 3000
HEALTHCHECK --interval=10s --timeout=3s --retries=5 \
  CMD ["wget", "-q", "-O", "/dev/null", "http://127.0.0.1:3000/"]
CMD ["node", "apps/web/server.js"]
