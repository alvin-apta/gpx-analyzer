FROM node:22-alpine AS build
WORKDIR /app
COPY package.json tsconfig.json index.html ./
RUN npm install
COPY src ./src
ARG VITE_MAP_STYLE_URL
ENV VITE_MAP_STYLE_URL=$VITE_MAP_STYLE_URL
RUN npm run build
FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
