# syntax=docker/dockerfile:1

# ---- stage 1: build the static files (this stage is not part of the final image) ----
FROM node:22-alpine AS build
WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

# Vite writes VITE_* variables into the JS at build time, not at runtime.
# Change it with: --build-arg VITE_API_BASE_URL=...  (or build.args in docker-compose.yml)
ARG VITE_API_BASE_URL=http://localhost:8000
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
RUN npm run build

# ---- stage 2: the published image: nginx serving dist/ ----
FROM nginx:alpine-slim
LABEL authors="maaari401"

# 'EOF' is quoted so docker doesn't touch nginx's $uri
COPY <<'EOF' /etc/nginx/conf.d/default.conf
server {
    listen 80;
    root /usr/share/nginx/html;

    # BrowserRouter: unknown paths (e.g. a reload on /bookings) get index.html,
    # and React Router shows the right page
    location / {
        try_files $uri $uri/ /index.html;
    }

    # Vite puts a hash in these file names, so the browser can cache them for good
    location /assets/ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
}
EOF

COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
