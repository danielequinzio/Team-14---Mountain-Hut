FROM node:22-alpine
LABEL authors="maaari"

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

EXPOSE 5173
# --host so vite listens on 0.0.0.0 and is reachable from outside the container
CMD ["npm", "run", "dev", "--", "--host"]