FROM node:22-alpine AS portal-build

WORKDIR /app/plexa_portal

COPY plexa_portal/package*.json ./
RUN npm ci

COPY plexa_portal ./

ARG VITE_APP_ENV=production
ARG VITE_API_BASE_URL=/api
ARG TARGET_API_VERSION=v1
ARG VITE_AUTH_MODE=dev
ARG VITE_ENABLE_DEV_LOGIN=false

ENV VITE_APP_ENV=$VITE_APP_ENV
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
ENV TARGET_API_VERSION=$TARGET_API_VERSION
ENV VITE_AUTH_MODE=$VITE_AUTH_MODE
ENV VITE_ENABLE_DEV_LOGIN=$VITE_ENABLE_DEV_LOGIN

RUN npm run build

FROM caddy:2-alpine

COPY deploy/Caddyfile /etc/caddy/Caddyfile
COPY --from=portal-build /app/plexa_portal/dist /srv
