FROM node:22-alpine AS dependencies

ENV PNPM_HOME=/pnpm
ENV PATH=$PNPM_HOME:$PATH
RUN corepack enable && corepack prepare pnpm@11.9.0 --activate
WORKDIR /workspace

COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY patches patches
COPY apps/web/package.json apps/web/package.json
COPY packages/shared/package.json packages/shared/package.json
RUN pnpm install --frozen-lockfile

FROM dependencies AS build

ARG ORYNTELA_ENVIRONMENT=development
ARG NEXT_PUBLIC_SITE_URL=http://localhost:3000
ARG NEXT_PUBLIC_APP_URL=http://localhost:3000
ARG NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
ARG AUTH_MODE=mock
ARG MOCK_AUTH_ENABLED=true
ARG NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY
ARG NEXT_PUBLIC_CLERK_JWT_TEMPLATE
ARG ORYNTELA_HSTS_ENABLED=false
ENV ORYNTELA_ENVIRONMENT=$ORYNTELA_ENVIRONMENT
ENV NEXT_PUBLIC_SITE_URL=$NEXT_PUBLIC_SITE_URL
ENV NEXT_PUBLIC_APP_URL=$NEXT_PUBLIC_APP_URL
ENV NEXT_PUBLIC_API_BASE_URL=$NEXT_PUBLIC_API_BASE_URL
ENV AUTH_MODE=$AUTH_MODE
ENV MOCK_AUTH_ENABLED=$MOCK_AUTH_ENABLED
ENV NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=$NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY
ENV NEXT_PUBLIC_CLERK_JWT_TEMPLATE=$NEXT_PUBLIC_CLERK_JWT_TEMPLATE
ENV ORYNTELA_HSTS_ENABLED=$ORYNTELA_HSTS_ENABLED

COPY apps/web apps/web
COPY packages/shared packages/shared
COPY docs/00-company/oryntela-privacy-policy.md docs/00-company/oryntela-privacy-policy.md
COPY docs/00-company/oryntela-terms-and-conditions.md docs/00-company/oryntela-terms-and-conditions.md
RUN pnpm build:web

FROM node:22-alpine AS runtime

ENV NODE_ENV=production
ENV PORT=8080
ENV HOSTNAME=0.0.0.0
WORKDIR /app
RUN addgroup --system --gid 1001 nodejs && adduser --system --uid 1001 nextjs

COPY --from=build --chown=nextjs:nodejs /workspace/apps/web/.next/standalone ./
COPY --from=build --chown=nextjs:nodejs /workspace/apps/web/.next/static ./apps/web/.next/static
COPY --from=build --chown=nextjs:nodejs /workspace/apps/web/public ./apps/web/public

USER nextjs
EXPOSE 8080
CMD ["node", "apps/web/server.js"]
