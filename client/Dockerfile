FROM node:24-alpine

WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .

EXPOSE 3000
# Host/port also on the command line so a config reload hiccup (e.g. during a git checkout)
# can never fall back to Vite defaults (localhost:5173, unreachable from the host).
CMD ["npm", "run", "dev", "--", "--config", "vite.config.js", "--host", "0.0.0.0", "--port", "3000", "--strictPort"]
