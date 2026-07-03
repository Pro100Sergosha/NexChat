# Build the React/Vite app, then serve the static bundle from nginx.
# The nginx site config is mounted from ../nginx/nginx.conf by docker-compose,
# so it stays authoritative in the repo and editable without a rebuild.
FROM node:20-alpine AS build
WORKDIR /app
COPY package.json ./
RUN npm install
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
