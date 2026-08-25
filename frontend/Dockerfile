FROM node:20-slim AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
# .env comes along with this COPY — Vite's build reads it directly, no build ARGs needed
# (and none are declared here on purpose: a declared-but-unset ARG becomes an empty-string
# env var for the RUN below, which Vite would then prefer over .env — see docker-compose.yml's
# note on the frontend service for the bug that caused).
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
