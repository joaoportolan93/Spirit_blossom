# Fase de build
FROM node:20-alpine AS builder

WORKDIR /app

ARG VITE_APP_NAME
ENV VITE_APP_NAME=$VITE_APP_NAME

COPY package.json package-lock.json ./
RUN npm ci

COPY . .
RUN npm run build

# Fase de produção — Nginx serve os estáticos
FROM nginx:1.27-alpine

COPY --from=builder /app/dist /usr/share/nginx/html

# Configuração SPA: redireciona 404 → index.html para o React Router
COPY nginx-spa.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]

