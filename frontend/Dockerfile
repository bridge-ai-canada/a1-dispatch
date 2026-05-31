# A1 Field Pro — Frontend (React 19 served by nginx)
# Multi-stage: yarn build → nginx:alpine

FROM node:20-alpine AS builder
WORKDIR /build

# Cache deps
COPY package.json yarn.lock ./
RUN yarn install --frozen-lockfile --network-timeout 600000

COPY . .

# Build-time env (override via --build-arg in CI)
ARG REACT_APP_BACKEND_URL=https://api.example.com
ENV REACT_APP_BACKEND_URL=$REACT_APP_BACKEND_URL
ENV NODE_OPTIONS=--max-old-space-size=4096
ENV GENERATE_SOURCEMAP=false

RUN yarn build

# ----- Runtime stage -----
FROM nginx:1.27-alpine AS runtime

# Run as non-root nginx
RUN apk add --no-cache curl tini

# Drop privileges — nginx default config writes to /var/cache/nginx etc.
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Strip default nginx index and copy SPA bundle
RUN rm -rf /usr/share/nginx/html/*
COPY --from=builder /build/build /usr/share/nginx/html

EXPOSE 8080

HEALTHCHECK --interval=15s --timeout=3s --retries=3 \
    CMD curl -fsS http://localhost:8080/healthz || exit 1

ENTRYPOINT ["/sbin/tini", "--"]
CMD ["nginx", "-g", "daemon off;"]
