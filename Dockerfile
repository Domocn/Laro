# Build stage — Vite (migrated off react-scripts/craco)
FROM node:20-alpine AS build

WORKDIR /app

# Dependencies first so source edits don't bust the install layer.
# Copy the lockfile too and prefer `npm ci` so the image resolves exactly the
# same tree as CI and local dev; fall back if a checkout has no lockfile.
COPY package.json package-lock.json* ./
RUN npm ci --no-audit --no-fund || npm install --no-audit --no-fund

# Source
COPY . .

# Build argument for backend URL - use placeholder for runtime injection.
# The real value is injected at container start by docker-entrypoint.sh.
ARG REACT_APP_BACKEND_URL=%REACT_APP_BACKEND_URL%
ENV REACT_APP_BACKEND_URL=$REACT_APP_BACKEND_URL
# Never ship source maps publicly — they expand attack surface and scanner noise
ENV GENERATE_SOURCEMAP=false

# Build the app
RUN npm run build

# Production stage
FROM nginx:alpine

# Copy built files (Vite outDir)
COPY --from=build /app/dist /usr/share/nginx/html

# Copy nginx config
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy entrypoint script
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

# Expose port
EXPOSE 80

ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["nginx", "-g", "daemon off;"]
